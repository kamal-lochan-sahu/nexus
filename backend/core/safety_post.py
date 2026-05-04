from typing import TypedDict, Any

class PostSafetyResult(TypedDict):
    safe: bool
    reason: str
    modified: bool
    command: dict

MAX_LINEAR_VELOCITY  = 0.5
MAX_ANGULAR_VELOCITY = 1.0
MAX_DISTANCE         = 5.0
MIN_CONFIDENCE       = 0.70
ARENA_HALF           = 3.0

def validate_command(command: dict) -> PostSafetyResult:
    cmd = dict(command)
    modified = False

    confidence = float(cmd.get("confidence", 1.0))
    if confidence < MIN_CONFIDENCE:
        return PostSafetyResult(safe=False, reason=f"Low confidence ({confidence:.2f}). Please rephrase your command.", modified=False, command=cmd)

    distance = float(cmd.get("distance", 0.0))
    if distance > MAX_DISTANCE:
        return PostSafetyResult(safe=False, reason=f"Distance {distance}m exceeds max {MAX_DISTANCE}m. Break into smaller steps.", modified=False, command=cmd)

    if distance > ARENA_HALF:
        return PostSafetyResult(safe=False, reason=f"Distance {distance}m may exceed arena boundary (+-{ARENA_HALF}m).", modified=False, command=cmd)

    velocity = float(cmd.get("velocity", 0.3))
    if velocity > MAX_LINEAR_VELOCITY:
        cmd["velocity"] = MAX_LINEAR_VELOCITY
        modified = True

    angular = float(cmd.get("angular_velocity", 0.5))
    if angular > MAX_ANGULAR_VELOCITY:
        cmd["angular_velocity"] = MAX_ANGULAR_VELOCITY
        modified = True

    reason = "ok"
    if modified:
        reason = f"Command approved. Velocity clamped to {MAX_LINEAR_VELOCITY} m/s."

    return PostSafetyResult(safe=True, reason=reason, modified=modified, command=cmd)

if __name__ == "__main__":
    tests = [
        {"action": "move_forward", "distance": 2.0, "velocity": 0.3, "confidence": 0.95},
        {"action": "move_forward", "distance": 10.0, "velocity": 0.3, "confidence": 0.90},
        {"action": "move_forward", "distance": 1.0, "velocity": 2.0, "confidence": 0.88},
        {"action": "turn_left",    "distance": 0.0, "velocity": 0.3, "confidence": 0.60},
        {"action": "move_forward", "distance": 4.0, "velocity": 0.3, "confidence": 0.85},
    ]
    for cmd in tests:
        r = validate_command(cmd)
        icon = "✅" if r["safe"] else "❌"
        mod = " [MODIFIED]" if r["modified"] else ""
        print(f"{icon}{mod} d={cmd.get('distance')}m v={cmd.get('velocity')} conf={cmd.get('confidence')} -> {r['reason']}")
