"""
human_safety.py - turns CoboSense output into a decision for motion commands.

Rules (fail-safe where it matters):
  - no sensor service running      -> motion allowed, but reported as "unavailable"
                                      (set NEXUS_REQUIRE_COBOSENSE=1 to block motion instead)
  - simulation mode (no camera)    -> the numbers are fake, so they must not throttle real commands
  - camera mode, data older than STALE_AFTER_SECONDS -> BLOCK (the sensor is blind)
  - camera mode, speed_multiplier 0 (human in stop zone) -> BLOCK
  - camera mode otherwise          -> allowed, speed scaled by the multiplier
"""
import math
from dataclasses import dataclass
from typing import Any, Optional

STALE_AFTER_SECONDS = 1.0


@dataclass(frozen=True)
class HumanSafety:
    allowed: bool
    multiplier: float
    status: str      # clear | simulated | unavailable | stale | stop | required_missing
    reason: str


def _clamp_multiplier(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return max(0.0, min(1.0, number))


def evaluate(service: Optional[Any], *, require: bool = False,
             stale_after: float = STALE_AFTER_SECONDS) -> HumanSafety:
    """`service` needs: .mode ("camera"/"simulation"), .age_seconds(), .current_payload (dict)."""
    if service is None:
        if require:
            return HumanSafety(False, 0.0, "required_missing", "Human-safety sensor is required but not running.")
        return HumanSafety(True, 1.0, "unavailable", "No human-safety sensor running.")

    if getattr(service, "mode", "camera") == "simulation":
        if require:
            return HumanSafety(False, 0.0, "required_missing", "Human-safety sensor is only simulating (no camera).")
        return HumanSafety(True, 1.0, "simulated", "Human-safety sensor is simulating; values ignored.")

    try:
        age = service.age_seconds()
    except Exception:  # noqa: BLE001
        age = None
    if age is None or age > stale_after:
        shown = "no data yet" if age is None else f"{age:.1f}s old"
        return HumanSafety(False, 0.0, "stale", f"Human-safety data is stale ({shown}); motion blocked.")

    payload = getattr(service, "current_payload", None) or {}
    multiplier = _clamp_multiplier(payload.get("speed_multiplier", 1.0))
    if multiplier <= 0.0:
        zone = payload.get("zone", "?")
        distance = payload.get("distance_m", "?")
        return HumanSafety(False, 0.0, "stop", f"Human in stop zone (zone {zone}, {distance} m); motion blocked.")
    return HumanSafety(True, multiplier, "clear", "ok")
