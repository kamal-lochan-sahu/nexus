"""
safety_post.py - validation of the parsed command (after the LLM).

Works on a flat command ({"action", "distance", "velocity", ...}) and also on the older nested
form ({"plan": [{"params": {...}}]}). Rejects NaN/inf/negative values, rejects distances above
the limit, and clamps velocities.
"""
import copy
import math
from typing import TypedDict


class PostSafetyResult(TypedDict):
    safe:     bool
    reason:   str
    modified: bool
    command:  dict


MAX_LINEAR_VELOCITY  = 0.5
MAX_ANGULAR_VELOCITY = 1.0
MAX_DISTANCE         = 5.0
MIN_CONFIDENCE       = 0.70
ARENA_HALF           = 3.0


def _finite(value, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number.")
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite.")
    return number


def _check_block(block: dict):
    """Validate and clamp motion parameters in place. Returns (modified, error)."""
    modified = False

    if "distance" in block:
        distance = _finite(block["distance"], "distance")
        if distance < 0:
            return modified, "Distance must not be negative."
        if distance > MAX_DISTANCE:
            return modified, f"Distance {distance}m exceeds max {MAX_DISTANCE}m."

    if "velocity" in block:
        velocity = _finite(block["velocity"], "velocity")
        if velocity < 0:
            return modified, "Velocity must not be negative (use a backward action instead)."
        if velocity > MAX_LINEAR_VELOCITY:
            block["velocity"] = MAX_LINEAR_VELOCITY
            modified = True

    if "angular_velocity" in block:
        angular = _finite(block["angular_velocity"], "angular_velocity")
        if abs(angular) > MAX_ANGULAR_VELOCITY:
            block["angular_velocity"] = math.copysign(MAX_ANGULAR_VELOCITY, angular)
            modified = True

    return modified, None


def _reject(reason: str, cmd: dict) -> PostSafetyResult:
    return PostSafetyResult(safe=False, reason=reason, modified=False, command=cmd)


def validate_command(command: dict) -> PostSafetyResult:
    cmd = copy.deepcopy(command)
    modified = False

    try:
        confidence = _finite(cmd.get("confidence", 1.0), "confidence")
        if confidence < MIN_CONFIDENCE:
            return _reject(f"Low confidence ({confidence:.2f}). Please rephrase.", cmd)

        changed, error = _check_block(cmd)
        if error:
            return _reject(error, cmd)
        modified = changed

        for step in cmd.get("plan", []) or []:
            if not isinstance(step, dict):
                return _reject("Malformed plan step.", cmd)
            params = step.get("params", {})
            if not isinstance(params, dict):
                return _reject("Malformed plan parameters.", cmd)
            changed, error = _check_block(params)
            if error:
                return _reject(error, cmd)
            modified = modified or changed
    except ValueError as exc:
        return _reject(str(exc), cmd)

    reason = "ok"
    if modified:
        reason = (f"Clamped to safety limits (max {MAX_LINEAR_VELOCITY} m/s, "
                  f"{MAX_ANGULAR_VELOCITY} rad/s).")

    return PostSafetyResult(safe=True, reason=reason, modified=modified, command=cmd)
