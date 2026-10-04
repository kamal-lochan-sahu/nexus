"""
safety_pre.py - pre-LLM input screening.

This is a coarse keyword filter, NOT a security boundary. The real guarantees come from
core.safety_post (limits on the parsed command) and the clamps inside the ROS bridge.
"""
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

MAX_INPUT_CHARS = 500
MIN_WORDS = 2

# Words that mean "halt now". Stopping is always safe, so these must never be blocked.
EMERGENCY_WORDS = frozenset({"stop", "halt", "freeze", "estop", "e-stop", "emergency"})
_EMERGENCY_FILLER = frozenset({"all", "now", "please", "robot", "robots", "everything",
                               "immediately", "the", "e"})
# One-word commands that are valid on their own.
SINGLE_WORD_COMMANDS = frozenset({"sit", "stand", "status"}) | EMERGENCY_WORDS

VAGUE_PATTERNS = [
    r"^\s*$",
    r"^.{1,3}$",
    r"^\W+$",
    r"^(uh+|um+|hm+|hmm+)$",
]

_TOKEN = re.compile(r"[a-z0-9-]+")


def _keyword_regex(keyword: str) -> "re.Pattern[str]":
    """Whole-word match ('hit' must not match 'white'). Single words may carry s/es/ed/ing."""
    words = [re.escape(w) for w in keyword.split()]
    body = r"\s+".join(words)
    suffix = r"(?:s|es|ed|ing)?" if len(words) == 1 else ""
    return re.compile(r"(?<![a-z0-9])" + body + suffix + r"(?![a-z0-9])")


_HARMFUL = [(kw, _keyword_regex(kw)) for kw in HARMFUL_KEYWORDS]


def is_emergency(user_input) -> bool:
    """True for short 'stop now' style phrases: 'stop', 'STOP ALL', 'e-stop', 'please halt now'."""
    if not isinstance(user_input, str):
        return False
    tokens = _TOKEN.findall(user_input.lower())
    if not tokens or len(tokens) > 5:
        return False
    if not all(t in EMERGENCY_WORDS or t in _EMERGENCY_FILLER for t in tokens):
        return False
    return any(t in EMERGENCY_WORDS for t in tokens)


def check_safety(user_input) -> SafetyResult:
    if not isinstance(user_input, str):
        return SafetyResult(safe=False, reason="Input must be text.")

    text = user_input.strip()
    if len(text) > MAX_INPUT_CHARS:
        return SafetyResult(safe=False, reason=f"Input too long (max {MAX_INPUT_CHARS} characters).")

    normalised = " ".join(text.lower().split())

    # Emergency and known one-word commands are valid even though they are short.
    if is_emergency(text) or normalised in SINGLE_WORD_COMMANDS:
        return SafetyResult(safe=True, reason="ok")

    for pattern in VAGUE_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return SafetyResult(safe=False, reason="Input too vague or empty. Please give a clear command.")

    word_count = len(text.split())
    if word_count < MIN_WORDS:
        return SafetyResult(safe=False, reason=f"Command too short ({word_count} word). Please describe what robot should do.")

    for keyword, regex in _HARMFUL:
        if regex.search(normalised):
            return SafetyResult(safe=False, reason=f"Unsafe command: keyword '{keyword}' is not allowed.")

    return SafetyResult(safe=True, reason="ok")


if __name__ == "__main__":
    for t in ["Walk forward 2 meters", "Kill the robot", "stop", "inspect the white box", "go", "!!!"]:
        r = check_safety(t)
        print(("OK  " if r["safe"] else "NO  "), repr(t).ljust(30), r["reason"])
