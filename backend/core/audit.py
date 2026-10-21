"""
audit.py - records /command outcomes in the database (command_log and safety_events).

A broken log must never break a command, so record_outcome() swallows every error.
The database functions are passed in, which keeps this module free of the database and easy to test.
"""
import math
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

MAX_TEXT_CHARS = 500
MAX_REASON_CHARS = 300


def _clip(value: Any, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _confidence(result: Dict[str, Any]) -> float:
    command = result.get("command")
    if not isinstance(command, dict):
        return 0.0
    try:
        value = float(command.get("confidence", 0.0))
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) else 0.0


def _blocked(result: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """(blocked_by, blocked_reason) for outcomes where the command did not run as asked."""
    status = result.get("status")
    if status in ("rejected", "blocked", "error"):
        return result.get("stage") or "unknown", _clip(result.get("reason"), MAX_REASON_CHARS) or None
    if status == "not_sent":
        return "bridge", _clip(result.get("reason"), MAX_REASON_CHARS) or None
    if status == "stop_failed":
        return "emergency", _clip(result.get("note"), MAX_REASON_CHARS) or None
    return None, None


def _safety_event(result: Dict[str, Any]) -> Optional[str]:
    stage, status = result.get("stage"), result.get("status")
    if stage == "emergency" and status in ("stopped", "stop_failed"):
        return "emergency_stop"
    if stage == "human_safety" and status == "blocked":
        return "human_safety_block"
    return None


async def record_outcome(
    user_text: Any,
    result: Any,
    *,
    log_command: Callable[..., Awaitable[None]],
    log_safety_event: Callable[..., Awaitable[None]],
) -> None:
    try:
        if not isinstance(result, dict):
            return
        command = result.get("command") if isinstance(result.get("command"), dict) else {}
        stage = result.get("stage")
        module = result.get("module") or ("emergency" if stage == "emergency" else "nl2rc")
        intent = command.get("action") or stage or "unknown"
        blocked_by, blocked_reason = _blocked(result)

        await log_command(
            _clip(user_text, MAX_TEXT_CHARS),
            str(module),
            str(intent),
            _confidence(result),
            str(result.get("status", "unknown")),
            blocked_by,
            blocked_reason,
        )

        event = _safety_event(result)
        if event:
            zone = str(result.get("human_safety") or "n/a")
            await log_safety_event(event, zone, 0.0, "unknown", 0.0, 0.0, 0)
    except Exception as exc:  # noqa: BLE001
        print(f"[NEXUS] could not record command: {exc!r}")
