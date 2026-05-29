"""
Step 7: Safety Validation — reuses NL2RC safety logic
VLA output same JSON schema as NL2RC + visual_context field
"""
import logging
logger = logging.getLogger(__name__)

MAX_VELOCITY = 0.4
MIN_APPROACH = 0.3
BLOCKED_ACTIONS = {"jump", "flip", "attack", "run"}

def validate(vla_output: dict) -> dict:
    """
    Input:  VLA JSON dict
    Output: same dict with safety_check updated
    Raises: ValueError if unsafe
    """
    issues = []
    plan = vla_output.get("plan", [])

    for step in plan:
        action = step.get("action", "")
        params = step.get("params", {})

        # Blocked actions
        if action in BLOCKED_ACTIONS:
            issues.append(f"blocked action: {action}")

        # Velocity check
        vel = params.get("velocity", 0)
        if vel > MAX_VELOCITY:
            logger.warning(f"Velocity {vel} > max {MAX_VELOCITY} — clamping")
            params["velocity"] = MAX_VELOCITY

        # Approach distance check
        dist = params.get("approach_distance", 0.5)
        if dist < MIN_APPROACH:
            logger.warning(f"approach_distance {dist} < min {MIN_APPROACH} — clamping")
            params["approach_distance"] = MIN_APPROACH

    if issues:
        vla_output["safety_check"] = f"BLOCKED: {'; '.join(issues)}"
        raise ValueError(f"Safety check failed: {issues}")

    vla_output["safety_check"] = "clear"
    logger.info("Safety check: CLEAR")
    return vla_output
