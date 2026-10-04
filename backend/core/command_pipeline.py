"""
command_pipeline.py - the /command flow, kept free of FastAPI so it can be unit-tested.

Order of work:
  1. emergency phrase ("stop", "halt", ...)  -> stop immediately, no LLM, no routing
  2. safety_pre (input screening)
  3. orchestrator routing (visual / fleet / navigation)
  4. LLM parse -> map the LLM *action* to a robot command (unknown actions are rejected)
  5. safety_post (limits) -> send to the robot -> arm a stop timer

Status values are honest: "executed" only when the bridge really accepted the command.
"""
import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from core.safety_post import MAX_LINEAR_VELOCITY, validate_command
from modules.nl2rc.safety_pre import check_safety, is_emergency

TURN_RATE = 0.5            # rad/s used for turn_left / turn_right
DEFAULT_MOVE_SECONDS = 2.0  # walk without a distance
DEFAULT_TURN_SECONDS = 1.0
MAX_MOTION_SECONDS = 20.0   # hard cap on any single motion

_DIRECTION_TO_ACTION = {
    "forward": "move_forward", "backward": "move_backward", "back": "move_backward",
    "left": "turn_left", "right": "turn_right",
}
_STATIONARY = {"stop", "sit", "stand", "status"}


# ── Mapping ───────────────────────────────────────────────────────

def plan_to_command(llm_result: dict) -> Tuple[Optional[dict], Optional[str], Optional[str]]:
    """LLM JSON -> flat command. Returns (command, error, warning). Never guesses an action."""
    plan = llm_result.get("plan")
    if not isinstance(plan, list) or not plan or not isinstance(plan[0], dict):
        return None, "LLM returned no usable plan.", None

    step = plan[0]
    warning = f"Only the first of {len(plan)} steps was used." if len(plan) > 1 else None
    action = str(step.get("action", "")).strip().lower()
    params = step.get("params")
    if not isinstance(params, dict):
        params = {}
    direction = str(params.get("direction", "")).strip().lower()

    if action in _STATIONARY:
        mapped = action
    elif action == "walk":
        mapped = _DIRECTION_TO_ACTION.get(direction or "forward")
        if mapped is None:
            return None, f"Unsupported walk direction '{direction}'.", None
    elif action == "turn":
        mapped = {"left": "turn_left", "right": "turn_right"}.get(direction)
        if mapped is None:
            return None, "A turn needs a direction: left or right.", None
    elif action in ("navigate", "inspect"):
        return None, (f"'{action}' cannot run as a direct command. "
                      "Say where to go (e.g. 'go to zone B') or what to inspect."), None
    else:
        return None, f"Unknown action '{action}'.", None

    try:
        command = {
            "action": mapped,
            "distance": float(params.get("distance", 0.0)),
            "velocity": float(params.get("velocity", 0.3)),
            "confidence": float(llm_result.get("confidence", 1.0)),
        }
    except (TypeError, ValueError):
        return None, "LLM returned a non-numeric distance, velocity or confidence.", None
    return command, None, warning


def command_to_velocity(command: dict) -> Tuple[float, float]:
    speed = min(abs(float(command.get("velocity", 0.0))), MAX_LINEAR_VELOCITY)
    action = command.get("action")
    if action == "move_forward":
        return speed, 0.0
    if action == "move_backward":
        return -speed, 0.0
    if action == "turn_left":
        return 0.0, TURN_RATE
    if action == "turn_right":
        return 0.0, -TURN_RATE
    return 0.0, 0.0


def motion_seconds(command: dict) -> float:
    """Time-based dead reckoning (no odometry): distance / speed, capped."""
    action = command.get("action")
    if action in ("move_forward", "move_backward"):
        speed = min(abs(float(command.get("velocity", 0.0))), MAX_LINEAR_VELOCITY)
        distance = float(command.get("distance", 0.0))
        seconds = distance / speed if distance > 0 and speed > 0 else DEFAULT_MOVE_SECONDS
    else:
        seconds = DEFAULT_TURN_SECONDS
    return min(seconds, MAX_MOTION_SECONDS)


# ── Robot I/O ─────────────────────────────────────────────────────

async def _ensure_connected(bridge) -> None:
    """The bridge never connects by itself; try once per command, off the event loop."""
    connect = getattr(bridge, "connect", None)
    if getattr(bridge, "connected", True) is False and callable(connect):
        try:
            await asyncio.get_running_loop().run_in_executor(None, connect)
        except Exception as exc:  # noqa: BLE001
            print(f"[NEXUS] bridge connect failed: {exc}")


async def _send(bridge, linear_x: float, angular_z: float) -> bool:
    await _ensure_connected(bridge)
    try:
        return bool(bridge.send_cmd_vel(linear_x=linear_x, angular_z=angular_z))
    except Exception as exc:  # noqa: BLE001
        print(f"[NEXUS] bridge send failed: {exc}")
        return False


async def _stop_robot(bridge) -> bool:
    await _ensure_connected(bridge)
    try:
        stop = getattr(bridge, "stop_robot", None)
        if callable(stop):
            return bool(stop())
        return bool(bridge.send_cmd_vel(linear_x=0.0, angular_z=0.0))
    except Exception as exc:  # noqa: BLE001
        print(f"[NEXUS] bridge stop failed: {exc}")
        return False


class _MotionWatchdog:
    """Sends a stop when a motion's time is up. A new motion or an emergency cancels the old timer."""

    def __init__(self) -> None:
        self._task: Optional["asyncio.Task[None]"] = None

    def cancel(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None

    def arm(self, seconds: float, bridge) -> None:
        self.cancel()
        self._task = asyncio.get_running_loop().create_task(self._run(seconds, bridge))

    @staticmethod
    async def _run(seconds: float, bridge) -> None:
        try:
            await asyncio.sleep(seconds)
            await _stop_robot(bridge)
        except asyncio.CancelledError:
            pass


_watchdog = _MotionWatchdog()


async def emergency_stop(get_orchestrator: Callable[[], Any], bridge) -> Dict[str, Any]:
    _watchdog.cancel()
    stopped = []
    delivered = await _stop_robot(bridge)
    if delivered:
        stopped.append("cmd_vel")
    try:
        get_orchestrator().stop_all()
        stopped.append("rl_policy")
    except Exception as exc:  # noqa: BLE001
        print(f"[NEXUS] orchestrator stop failed: {exc}")

    note = "The fleet scheduler is not halted by this path."
    if not delivered:
        note = "Stop could not be delivered to the robot (bridge offline). " + note
    return {
        "status": "stopped" if stopped else "stop_failed",
        "stage": "emergency",
        "stopped": stopped,
        "robot_connected": delivered,
        "note": note,
    }


# ── Main entry ────────────────────────────────────────────────────

async def execute_command(
    user_text: Any,
    *,
    call_llm: Callable[[str], Awaitable[dict]],
    get_orchestrator: Callable[[], Any],
    bridge,
) -> Dict[str, Any]:
    text = user_text if isinstance(user_text, str) else ""

    # 1. Emergency phrase: never waits for the LLM or the router.
    if is_emergency(text):
        return await emergency_stop(get_orchestrator, bridge)

    # 2. Input screening
    pre = check_safety(text)
    if not pre["safe"]:
        return {"status": "rejected", "stage": "safety_pre", "reason": pre["reason"]}

    # 3. Orchestrator routing (visual / fleet / navigation); one shared instance
    try:
        routed = get_orchestrator().handle(text)
        if routed.get("module", "nl2rc") != "nl2rc":
            return {"status": "ok", "stage": "orchestrated", "module": routed.get("module"), "result": routed}
    except Exception as exc:  # noqa: BLE001
        print(f"[NEXUS] Orchestrator fallback: {exc}")

    # 4. LLM parse and mapping
    llm_result = await call_llm(text)
    if not isinstance(llm_result, dict) or "error" in llm_result:
        reason = llm_result.get("error") if isinstance(llm_result, dict) else "bad LLM response"
        return {"status": "error", "stage": "llm", "reason": reason}

    command, error, warning = plan_to_command(llm_result)
    if error:
        return {"status": "rejected", "stage": "planner", "reason": error}

    # 5. Limits
    post = validate_command(command)
    if not post["safe"]:
        return {"status": "rejected", "stage": "safety_post", "reason": post["reason"]}
    final = post["command"]
    action = final["action"]

    if action == "stop":
        return await emergency_stop(get_orchestrator, bridge)
    if action == "status":
        return {"status": "ok", "stage": "status", "command": final, "reason": "Status request; no motion."}
    if action in ("sit", "stand"):
        return {"status": "rejected", "stage": "planner",
                "reason": "Posture commands (sit/stand) are not wired to the robot yet."}

    linear_x, angular_z = command_to_velocity(final)
    sent = await _send(bridge, linear_x, angular_z)
    if sent:
        _watchdog.arm(motion_seconds(final), bridge)

    response: Dict[str, Any] = {
        "status": "executed" if sent else "not_sent",
        "command": final,
        "modified": post["modified"],
        "reason": post["reason"] if sent else "Validated but not sent: robot bridge is offline.",
        "sent": sent,
    }
    if warning:
        response["warning"] = warning
    return response
