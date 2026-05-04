import json
import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator

class RobotCommand(BaseModel):
    action: str = Field(..., description="Robot action type")
    distance: float = Field(default=0.0, ge=0.0)
    velocity: float = Field(default=0.3, gt=0.0, le=2.0)
    angular_velocity: float = Field(default=0.5, ge=0.0)
    angle: float = Field(default=0.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    duration: Optional[float] = Field(default=None, ge=0.0)

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"move_forward", "move_backward", "turn_left", "turn_right", "stop", "rotate", "stand", "sit"}
        if v not in allowed:
            raise ValueError(f"Unknown action '{v}'. Allowed: {allowed}")
        return v

def _extract_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text.strip()

class ParseResult:
    def __init__(self, success, command, error, raw_json):
        self.success  = success
        self.command  = command
        self.error    = error
        self.raw_json = raw_json

    def __repr__(self):
        if self.success:
            return f"ParseResult(✅ {self.command.action} d={self.command.distance}m)"
        return f"ParseResult(❌ {self.error})"

def parse_llm_output(llm_text: str) -> ParseResult:
    json_str = _extract_json(llm_text)
    try:
        raw_dict = json.loads(json_str)
    except json.JSONDecodeError as e:
        return ParseResult(False, None, f"JSON parse failed: {e}", None)
    try:
        command = RobotCommand(**raw_dict)
        return ParseResult(True, command, None, raw_dict)
    except Exception as e:
        return ParseResult(False, None, f"Validation failed: {e}", raw_dict)

if __name__ == "__main__":
    tests = [
        '{"action": "move_forward", "distance": 2.0, "velocity": 0.3, "confidence": 0.95}',
        '```json\n{"action": "turn_left", "angle": 90, "velocity": 0.3, "confidence": 0.88}\n```',
        'Here is the command: {"action": "stop", "confidence": 0.99} execute this.',
        '{"action": "move_forward", "distance": }',
        '{"action": "fly_up", "distance": 2.0, "confidence": 0.90}',
        'I cannot process this.',
    ]
    for i, t in enumerate(tests, 1):
        r = parse_llm_output(t)
        print(f"Test {i}: {r}")
        if not r.success:
            print(f"  Error: {r.error}")
