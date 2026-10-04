"""Tests for the command safety path: safety_pre, safety_post, action mapping, pipeline."""
import asyncio

import pytest

from core import command_pipeline as cp
from core.safety_post import validate_command
from modules.nl2rc.safety_pre import check_safety, is_emergency


# ── helpers ───────────────────────────────────────────────────────

class FakeBridge:
    def __init__(self, accept=True):
        self.accept = accept
        self.connected = True
        self.calls = []

    def send_cmd_vel(self, linear_x=0.0, angular_z=0.0, **_):
        self.calls.append((linear_x, angular_z))
        return self.accept

    def stop_robot(self, **_):
        return self.send_cmd_vel(0.0, 0.0)


class FakeOrch:
    def __init__(self, route=None):
        self.route = route
        self.stopped = 0

    def handle(self, text):
        return {"module": self.route} if self.route else {"module": "nl2rc"}

    def stop_all(self):
        self.stopped += 1


def llm_returning(plan, confidence=0.95):
    async def _llm(_text):
        return {"intent": "x", "plan": plan, "confidence": confidence}
    return _llm


async def llm_must_not_run(_text):
    raise AssertionError("LLM must not be called")


def run(text, llm, orch=None, bridge=None):
    orch = orch or FakeOrch()
    bridge = bridge or FakeBridge()
    result = asyncio.run(cp.execute_command(text, call_llm=llm, get_orchestrator=lambda: orch, bridge=bridge))
    return result, orch, bridge


def walk(**params):
    return [{"step": 1, "action": "walk", "params": {"direction": "forward", **params}}]


# ── safety_pre ────────────────────────────────────────────────────

@pytest.mark.parametrize("text", ["stop", "STOP", "stop all", "Stop now!", "e-stop", "emergency stop",
                                  "halt", "please stop the robot", "freeze"])
def test_emergency_phrases_are_safe_and_detected(text):
    assert check_safety(text)["safe"] is True
    assert is_emergency(text) is True


@pytest.mark.parametrize("text", ["go to the bus stop", "walk forward then stop", "walk forward 2 meters", "", None, 42])
def test_not_emergency(text):
    assert is_emergency(text) is False


def test_white_is_not_hit():
    assert check_safety("inspect the white box")["safe"] is True


@pytest.mark.parametrize("text", ["hit the wall", "kill the process", "ram into the wall", "disable   safety now",
                                  "sudo move", "crashing into it", "go to admin panel"])
def test_harmful_still_blocked(text):
    assert check_safety(text)["safe"] is False


def test_harmless_words_pass():
    assert check_safety("move forward harmlessly")["safe"] is True


@pytest.mark.parametrize("text", ["sit", "stand", "status"])
def test_single_word_commands_allowed(text):
    assert check_safety(text)["safe"] is True


@pytest.mark.parametrize("text", ["", "   ", "go", "!!!", "um", "walk", None, 7])
def test_vague_or_invalid_rejected(text):
    assert check_safety(text)["safe"] is False


def test_too_long_rejected():
    assert check_safety("walk forward " * 100)["safe"] is False


# ── safety_post ───────────────────────────────────────────────────

def flat(**kw):
    return {"action": "move_forward", "distance": 1.0, "velocity": 0.3, "confidence": 0.95, **kw}


def test_flat_overspeed_is_clamped_and_flagged():
    post = validate_command(flat(velocity=3.0))
    assert post["safe"] and post["modified"] and post["command"]["velocity"] == 0.5


def test_flat_distance_over_limit_rejected():
    assert validate_command(flat(distance=6.0))["safe"] is False


@pytest.mark.parametrize("bad", [{"velocity": -0.2}, {"distance": -1.0}, {"velocity": float("nan")},
                                 {"distance": float("inf")}, {"velocity": "fast"}, {"confidence": float("nan")}])
def test_bad_numbers_rejected(bad):
    assert validate_command(flat(**bad))["safe"] is False


def test_low_confidence_rejected():
    assert validate_command(flat(confidence=0.4))["safe"] is False


def test_nested_plan_still_validated():
    post = validate_command({"confidence": 0.9, "plan": [{"params": {"velocity": 2.0, "distance": 1.0}}]})
    assert post["safe"] and post["modified"]
    assert post["command"]["plan"][0]["params"]["velocity"] == 0.5
    assert validate_command({"confidence": 0.9, "plan": [{"params": {"distance": 9.0}}]})["safe"] is False


def test_validate_does_not_mutate_input():
    original = flat(velocity=3.0)
    validate_command(original)
    assert original["velocity"] == 3.0


# ── plan_to_command ───────────────────────────────────────────────

@pytest.mark.parametrize("action,expected", [("stop", "stop"), ("sit", "sit"), ("stand", "stand"), ("status", "status")])
def test_stationary_actions_keep_their_meaning(action, expected):
    cmd, err, _ = cp.plan_to_command({"plan": [{"action": action, "params": {}}], "confidence": 0.9})
    assert err is None and cmd["action"] == expected


@pytest.mark.parametrize("action,direction,expected", [
    ("walk", "forward", "move_forward"), ("walk", "backward", "move_backward"),
    ("walk", "", "move_forward"), ("walk", "left", "turn_left"),
    ("turn", "left", "turn_left"), ("turn", "right", "turn_right"),
])
def test_motion_mapping(action, direction, expected):
    cmd, err, _ = cp.plan_to_command({"plan": [{"action": action, "params": {"direction": direction}}]})
    assert err is None and cmd["action"] == expected


@pytest.mark.parametrize("plan", [
    [{"action": "fly", "params": {}}], [{"action": "turn", "params": {}}],
    [{"action": "navigate", "params": {}}], [{"action": "inspect", "params": {}}],
    [{"action": "walk", "params": {"direction": "sideways"}}], [], None, "oops", [None],
])
def test_unknown_or_unusable_plans_are_rejected(plan):
    cmd, err, _ = cp.plan_to_command({"plan": plan})
    assert cmd is None and err


def test_non_numeric_parameter_rejected():
    cmd, err, _ = cp.plan_to_command({"plan": [{"action": "walk", "params": {"distance": "2 meters"}}]})
    assert cmd is None and err


def test_multi_step_plan_gives_warning():
    plan = walk() + [{"step": 2, "action": "turn", "params": {"direction": "left"}}]
    cmd, err, warning = cp.plan_to_command({"plan": plan})
    assert err is None and cmd["action"] == "move_forward" and "first of 2" in warning


def test_velocity_and_duration_helpers():
    assert cp.command_to_velocity({"action": "move_forward", "velocity": 9}) == (0.5, 0.0)
    assert cp.command_to_velocity({"action": "move_backward", "velocity": 0.3}) == (-0.3, 0.0)
    assert cp.command_to_velocity({"action": "turn_left", "velocity": 0.3}) == (0.0, 0.5)
    assert cp.command_to_velocity({"action": "stop"}) == (0.0, 0.0)
    assert cp.motion_seconds({"action": "move_forward", "velocity": 0.5, "distance": 1.0}) == pytest.approx(2.0)
    assert cp.motion_seconds({"action": "move_forward", "velocity": 0.3, "distance": 0.0}) == cp.DEFAULT_MOVE_SECONDS
    assert cp.motion_seconds({"action": "move_forward", "velocity": 0.01, "distance": 5.0}) == cp.MAX_MOTION_SECONDS


# ── pipeline ──────────────────────────────────────────────────────

def test_emergency_phrase_skips_llm_and_stops_everything():
    result, orch, bridge = run("STOP ALL", llm_must_not_run)
    assert result["status"] == "stopped" and result["stopped"] == ["cmd_vel", "rl_policy"]
    assert orch.stopped == 1 and bridge.calls == [(0.0, 0.0)]


def test_emergency_reports_when_robot_unreachable():
    result, orch, _ = run("stop", llm_must_not_run, bridge=FakeBridge(accept=False))
    assert result["status"] == "stopped" and result["robot_connected"] is False
    assert "offline" in result["note"] and orch.stopped == 1


def test_llm_stop_action_is_a_real_stop_not_forward():
    result, orch, bridge = run("please halt all movement", llm_returning([{"step": 1, "action": "stop", "params": {}}]))
    assert result["status"] == "stopped" and orch.stopped == 1
    assert all(call == (0.0, 0.0) for call in bridge.calls)


def test_walk_forward_is_sent_and_reported_executed():
    result, _, bridge = run("walk forward 1 meter", llm_returning(walk(distance=1.0, velocity=0.3)))
    assert result["status"] == "executed" and result["sent"] is True
    assert bridge.calls[0] == (0.3, 0.0)


def test_overspeed_is_clamped_before_sending():
    result, _, bridge = run("walk forward fast", llm_returning(walk(distance=1.0, velocity=3.0)))
    assert result["status"] == "executed" and result["modified"] is True
    assert bridge.calls[0] == (0.5, 0.0)


def test_turn_right_sends_negative_angular():
    plan = [{"step": 1, "action": "turn", "params": {"direction": "right"}}]
    _, _, bridge = run("turn right now please", llm_returning(plan))
    assert bridge.calls[0] == (0.0, -0.5)


def test_offline_bridge_is_not_reported_as_executed():
    result, _, bridge = run("walk forward 1 meter", llm_returning(walk(distance=1.0)), bridge=FakeBridge(accept=False))
    assert result["status"] == "not_sent" and result["sent"] is False


def test_too_far_is_rejected_and_nothing_is_sent():
    result, _, bridge = run("walk forward a lot", llm_returning(walk(distance=50.0)))
    assert result["status"] == "rejected" and result["stage"] == "safety_post" and bridge.calls == []


def test_low_confidence_is_rejected():
    result, _, bridge = run("walk forward", llm_returning(walk(), confidence=0.2))
    assert result["status"] == "rejected" and bridge.calls == []


def test_sit_is_rejected_honestly_not_turned_into_motion():
    result, _, bridge = run("sit down please", llm_returning([{"step": 1, "action": "sit", "params": {}}]))
    assert result["status"] == "rejected" and "not wired" in result["reason"] and bridge.calls == []


def test_status_request_moves_nothing():
    result, _, bridge = run("what is your status", llm_returning([{"step": 1, "action": "status", "params": {}}]))
    assert result["status"] == "ok" and bridge.calls == []


def test_unsafe_text_never_reaches_llm_or_robot():
    result, _, bridge = run("hit the wall hard", llm_must_not_run)
    assert result["status"] == "rejected" and result["stage"] == "safety_pre" and bridge.calls == []


def test_orchestrator_route_short_circuits_llm():
    result, _, bridge = run("patrol the factory floor", llm_must_not_run, orch=FakeOrch(route="flexcell"))
    assert result["stage"] == "orchestrated" and result["module"] == "flexcell" and bridge.calls == []


def test_orchestrator_failure_falls_back_to_llm():
    class Broken:
        def handle(self, _):
            raise RuntimeError("boom")
    result, _, bridge = run("walk forward 1 meter", llm_returning(walk(distance=1.0)), orch=Broken())
    assert result["status"] == "executed"


def test_llm_error_is_reported():
    async def failing(_):
        return {"error": "Groq API error: down"}
    result, _, bridge = run("walk forward 1 meter", failing)
    assert result["status"] == "error" and result["stage"] == "llm" and bridge.calls == []


def test_multi_step_plan_executes_first_step_with_warning():
    plan = walk(distance=1.0) + [{"step": 2, "action": "turn", "params": {"direction": "left"}}]
    result, _, bridge = run("walk forward then turn left", llm_returning(plan))
    assert result["status"] == "executed" and "warning" in result and len(bridge.calls) == 1


def test_motion_stops_itself_when_time_is_up():
    async def scenario():
        bridge, orch = FakeBridge(), FakeOrch()
        result = await cp.execute_command("walk forward a bit", call_llm=llm_returning(walk(distance=0.03, velocity=0.3)),
                                          get_orchestrator=lambda: orch, bridge=bridge)
        assert result["status"] == "executed" and bridge.calls == [(0.3, 0.0)]
        await asyncio.sleep(0.4)           # 0.03 m / 0.3 m/s = 0.1 s
        return bridge.calls
    assert asyncio.run(scenario())[-1] == (0.0, 0.0)


def test_emergency_cancels_pending_stop_timer():
    async def scenario():
        bridge, orch = FakeBridge(), FakeOrch()
        await cp.execute_command("walk forward a bit", call_llm=llm_returning(walk(distance=5.0, velocity=0.5)),
                                 get_orchestrator=lambda: orch, bridge=bridge)
        await cp.execute_command("stop", call_llm=llm_must_not_run, get_orchestrator=lambda: orch, bridge=bridge)
        count = len(bridge.calls)
        assert cp._watchdog._task is None
        return count
    assert asyncio.run(scenario()) == 2   # one motion + one stop, no extra timer stop


def test_bridge_is_connected_on_demand():
    class Lazy(FakeBridge):
        def __init__(self):
            super().__init__()
            self.connected = False
            self.connect_calls = 0

        def connect(self):
            self.connect_calls += 1
            self.connected = True
            return True

    bridge = Lazy()
    result, _, _ = run("walk forward 1 meter", llm_returning(walk(distance=1.0)), bridge=bridge)
    assert bridge.connect_calls == 1 and result["status"] == "executed"
