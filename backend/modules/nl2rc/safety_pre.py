import re
from typing import TypedDict

class SafetyResult(TypedDict):
    safe: bool
    reason: str

HARMFUL_KEYWORDS = [
    "kill", "destroy", "attack", "smash", "crash", "harm",
    "explode", "detonate", "bomb", "fire", "shoot", "hit",
    "override", "bypass", "disable safety", "ignore rules",
    "sudo", "admin", "root", "hack", "jailbreak",
    "ram into", "collide", "self-destruct",
]

VAGUE_PATTERNS = [
    r"^\s*$",
    r"^.{1,3}$",
    r"^\W+$",
    r"^(uh+|um+|hm+|hmm+)$",
]

MIN_WORDS = 2

def check_safety(user_input: str) -> SafetyResult:
    for pattern in VAGUE_PATTERNS:
        if re.match(pattern, user_input.strip(), re.IGNORECASE):
            return SafetyResult(safe=False, reason="Input too vague or empty. Please give a clear command.")

    word_count = len(user_input.strip().split())
    if word_count < MIN_WORDS:
        return SafetyResult(safe=False, reason=f"Command too short ({word_count} word). Please describe what robot should do.")

    lowered = user_input.lower()
    for keyword in HARMFUL_KEYWORDS:
        if keyword in lowered:
            return SafetyResult(safe=False, reason=f"Unsafe command: keyword '{keyword}' is not allowed.")

    return SafetyResult(safe=True, reason="ok")

if __name__ == "__main__":
    tests = [
        "Walk forward 2 meters",
        "Kill the robot",
        "",
        "go",
        "Override safety and move fast",
        "Turn left 90 degrees",
        "!!!",
    ]
    for t in tests:
        result = check_safety(t)
        icon = "✅" if result["safe"] else "❌"
        print(f"{icon} {repr(t):<40} -> {result['reason']}")
