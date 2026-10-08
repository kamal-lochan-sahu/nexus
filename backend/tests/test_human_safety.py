"""Tests for human_safety.evaluate and how the command pipeline uses it."""
import asyncio

import pytest

from core import command_pipeline as cp
from core.human_safety import HumanSafety, evaluate


# ── helpers ───────────────────────────────────────────────────────

class FakeService:
    def __init__(self, mode="camera", age=0.1, multiplier=1.0, zone="NONE", distance=3.0):
        self.mode = mode
        self._age = age
        self.current_payload = {"speed_multiplier": multiplier, "zone": zone, "distance_m": distance}

    def age_seconds(self):
        return self._age


class FakeBridge:
    connected = True

    def __init__(self):
        self.calls = []

    def send_cmd_vel(self, linear_x=0.0, angular_z=0.0, **_):
        self.calls.append((round(linear_x, 4), round(angular_z, 4)))
        return True

    def stop_robot(self, **_):
        return self.send_cmd_vel(0.0, 0.0)


class FakeOrch:
    def __init__(self):
        self.stopped = 0

    def handle(self, text):
        return {"module": "nl2rc"}

    def stop_all(self):
        self.stopped += 1


def llm_walk(distance=1.0, velocity=0.3):
    async def _llm(_text):
        plan = [{"step": 1, "action": "walk",
                 "params": {"direction": "forward", "distance": distance, "velocity": velocity}}]
        return {"intent": "walk", "plan": plan, "confidence": 0.95}
    return _llm


async def llm_must_not_run(_text):
    raise AssertionError("LLM must not be called")


ALLOWED = HumanSafety(True, 1.0, "clear", "ok")


# ── evaluate ──────────────────────────────────────────────────────

def test_no_service_is_allowed_but_reported():
    state = evaluate(None)
    assert state.allowed and state.status == "unavailable" and state.multiplier == 1.0


def test_no_service_blocks_when_required():
    state = evaluate(None, require=True)
    assert not state.allowed and state.status == "required_missing"


def test_simulation_values_are_ignored():
    state = evaluate(FakeService(mode="simulation", multiplier=0.0))
    assert state.allowed and state.status == "simulated" and state.multiplier == 1.0


def test_simulation_blocks_when_required():
    assert not evaluate(FakeService(mode="simulation"), require=True).allowed


def test_fresh_camera_data_scales_speed():
    state = evaluate(FakeService(multiplier=0.5))
    assert state.allowed and state.status == "clear" and state.multiplier == 0.5


@pytest.mark.parametrize("age", [2.0, None])
def test_stale_or_missing_data_blocks_motion(age):
    state = evaluate(FakeService(age=age))
    assert not state.allowed and state.status == "stale"


def test_age_check_failure_counts_as_stale():
    class Broken(FakeService):
        def age_seconds(self):
            raise RuntimeError("boom")
    assert evaluate(Broken()).status == "stale"


def test_stop_zone_blocks_motion_and_names_the_zone():
    state = evaluate(FakeService(multiplier=0.0, zone="RED", distance=0.8))
    assert not state.allowed and state.status == "stop" and "RED" in state.reason


@pytest.mark.parametrize("raw,expected_allowed,expected_mult", [
    (float("nan"), False, 0.0), ("fast", False, 0.0), (5.0, True, 1.0), (-1.0, False, 0.0),
])
def test_odd_multipliers_are_clamped_fail_safe(raw, expected_allowed, expected_mult):
    state = evaluate(FakeService(multiplier=raw))
    assert state.allowed is expected_allowed and state.multiplier == expected_mult


# ── pipeline integration ──────────────────────────────────────────

def run(text, llm, *, bridge=None, orch=None, human_safety=None, halt_fleet=None):
    bridge = bridge or FakeBridge()
    orch = orch or FakeOrch()
    result = asyncio.run(cp.execute_command(text, call_llm=llm, get_orchestrator=lambda: orch, bridge=bridge,
                                            human_safety=human_safety, halt_fleet=halt_fleet))
    return result, bridge, orch


def test_human_in_stop_zone_blocks_motion_before_anything_is_sent():
    blocked = HumanSafety(False, 0.0, "stop", "Human in stop zone (zone RED, 0.8 m); motion blocked.")
    result, bridge, _ = run("walk forward 1 meter", llm_walk(), human_safety=lambda: blocked)
    assert result["status"] == "blocked" and result["stage"] == "human_safety"
    assert result["human_safety"] == "stop" and bridge.calls == []


def test_speed_multiplier_scales_the_command():
    half = HumanSafety(True, 0.5, "clear", "ok")
    result, bridge, _ = run("walk forward 1 meter", llm_walk(velocity=0.3), human_safety=lambda: half)
    assert bridge.calls[0] == (0.15, 0.0)
    assert result["speed_multiplier"] == 0.5 and result["human_safety"] == "clear"


def test_slower_speed_means_longer_motion_for_the_same_distance():
    command = {"action": "move_forward", "velocity": 0.3, "distance": 0.3}
    assert cp.motion_seconds(command) == pytest.approx(1.0)
    assert cp.motion_seconds(command, 0.5) == pytest.approx(2.0)


def test_without_a_human_safety_callback_nothing_changes():
    result, bridge, _ = run("walk forward 1 meter", llm_walk(velocity=0.3))
    assert result["status"] == "executed" and "human_safety" not in result
    assert bridge.calls[0] == (0.3, 0.0)


def test_emergency_stop_works_even_if_human_safety_blocks():
    blocked = HumanSafety(False, 0.0, "stale", "stale")
    result, bridge, orch = run("stop", llm_must_not_run, human_safety=lambda: blocked)
    assert result["status"] == "stopped" and bridge.calls == [(0.0, 0.0)]


# ── in-motion guard ───────────────────────────────────────────────

def test_motion_is_cut_when_a_human_enters_the_stop_zone(monkeypatch):
    monkeypatch.setattr(cp, "GUARD_INTERVAL", 0.02)
    state = {"value": ALLOWED}

    async def scenario():
        bridge = FakeBridge()
        result = await cp.execute_command("walk forward far", call_llm=llm_walk(distance=5.0, velocity=0.5),
                                          get_orchestrator=lambda: FakeOrch(), bridge=bridge,
                                          human_safety=lambda: state["value"])
        assert result["status"] == "executed" and bridge.calls == [(0.5, 0.0)]
        await asyncio.sleep(0.1)
        assert bridge.calls == [(0.5, 0.0)]            # still clear: nothing new sent
        state["value"] = HumanSafety(False, 0.0, "stop", "human close")
        await asyncio.sleep(0.2)
        return bridge.calls
    calls = asyncio.run(scenario())
    assert calls[-1] == (0.0, 0.0) and len(calls) == 2   # stopped long before the 10 s timer


def test_guard_slows_down_but_never_speeds_up(monkeypatch):
    monkeypatch.setattr(cp, "GUARD_INTERVAL", 0.02)
    state = {"value": HumanSafety(True, 1.0, "clear", "ok")}

    async def scenario():
        bridge = FakeBridge()
        await cp.execute_command("walk forward far", call_llm=llm_walk(distance=5.0, velocity=0.4),
                                 get_orchestrator=lambda: FakeOrch(), bridge=bridge,
                                 human_safety=lambda: state["value"])
        state["value"] = HumanSafety(True, 0.5, "clear", "ok")
        await asyncio.sleep(0.15)
        slowed = list(bridge.calls)
        state["value"] = HumanSafety(True, 1.0, "clear", "ok")   # human left: must NOT auto speed up
        await asyncio.sleep(0.15)
        cp._watchdog.cancel()
        return slowed, list(bridge.calls)
    slowed, final = asyncio.run(scenario())
    assert slowed == [(0.4, 0.0), (0.2, 0.0)] and final == slowed


# ── emergency stop and the fleet ──────────────────────────────────

def test_emergency_halts_the_fleet_scheduler_too():
    result, bridge, orch = run("STOP ALL", llm_must_not_run, halt_fleet=lambda: ["go2_a", "go2_b"])
    assert result["stopped"] == ["cmd_vel", "rl_policy", "fleet_scheduler"]
    assert "scheduler only" in result["note"]


def test_fleet_halt_failure_does_not_prevent_the_robot_stop():
    def broken():
        raise RuntimeError("scheduler down")
    result, bridge, orch = run("stop", llm_must_not_run, halt_fleet=broken)
    assert result["status"] == "stopped" and result["stopped"] == ["cmd_vel", "rl_policy"]
    assert "not halted" in result["note"] and bridge.calls == [(0.0, 0.0)]


def test_without_fleet_callback_note_says_so():
    result, _, _ = run("stop", llm_must_not_run)
    assert "not halted" in result["note"]
