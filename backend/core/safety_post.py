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

def validate_command(command: dict) -> PostSafetyResult:
    import copy
    cmd      = copy.deepcopy(command)
    modified = False

    # Confidence check
    confidence = float(cmd.get("confidence", 1.0))
    if confidence < MIN_CONFIDENCE:
        return PostSafetyResult(
            safe=False,
            reason=f"Low confidence ({confidence:.2f}). Please rephrase.",
            modified=False, command=cmd)

    # Plan ke andar har step check karo
    for step in cmd.get("plan", []):
        params = step.get("params", {})

        # Distance check
        distance = float(params.get("distance", 0.0))
        if distance > MAX_DISTANCE:
            return PostSafetyResult(
                safe=False,
                reason=f"Distance {distance}m exceeds max {MAX_DISTANCE}m.",
                modified=False, command=cmd)

        # Velocity clamp
        velocity = float(params.get("velocity", 0.3))
        if velocity > MAX_LINEAR_VELOCITY:
            params["velocity"] = MAX_LINEAR_VELOCITY
            modified = True

        # Angular velocity clamp
        angular = float(params.get("angular_velocity", 0.0))
        if angular > MAX_ANGULAR_VELOCITY:
            params["angular_velocity"] = MAX_ANGULAR_VELOCITY
            modified = True

    reason = "ok"
    if modified:
        reason = f"Velocity clamped to {MAX_LINEAR_VELOCITY} m/s."

    return PostSafetyResult(
        safe=True, reason=reason,
        modified=modified, command=cmd)
