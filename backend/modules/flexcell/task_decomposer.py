"""
FlexCell — Step 1: Task Decomposer
High-level goal → structured JSON task list via Groq LLM
"""

import json
import logging
from pathlib import Path
from typing import Optional

from groq import AsyncGroq
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

# ─── Models ─────────────────────────────────────────────────────────────────

class TaskItem(BaseModel):
    robot:    str   # "go2_a" | "go2_b"
    task:     str   # PATROL | INSPECT | ESCORT | GUARD | CHARGE
    priority: int   # 1 = highest, 5 = lowest
    params:   dict  # zone, speed, target, etc.

    @field_validator("robot")
    @classmethod
    def validate_robot(cls, v):
        if v not in ("go2_a", "go2_b"):
            raise ValueError(f"Invalid robot: {v}")
        return v

    @field_validator("task")
    @classmethod
    def validate_task(cls, v):
        allowed = {"PATROL", "INSPECT", "ESCORT", "GUARD", "CHARGE"}
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"Invalid task: {v}. Allowed: {allowed}")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        if not (1 <= v <= 5):
            raise ValueError(f"Priority must be 1-5, got {v}")
        return v


class DecompositionResult(BaseModel):
    tasks:      list[TaskItem]
    raw_goal:   str
    confidence: float
    reasoning:  Optional[str] = None


# ─── System prompt ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a multi-robot task planner for a factory floor.

You have TWO robots: go2_a and go2_b.

ZONES (6x6m arena):
  Zone A: top-left     x[-3,0],  y[0,+3]
  Zone B: top-right    x[0,+3],  y[0,+3]
  Zone C: bottom-left  x[-3,0],  y[-3,0]
  Zone D: bottom-right x[0,+3],  y[-3,0]

TASK TYPES:
  PATROL  - systematically cover an area
  INSPECT - check a specific location once
  ESCORT  - follow a human safely
  GUARD   - hold position in a zone
  CHARGE  - return robot to charging dock

RULES:
  1. Distribute work evenly between go2_a and go2_b
  2. Never assign both robots to the exact same zone simultaneously
  3. Priority 1 = most urgent, 5 = least urgent
  4. If task needs only one robot, assign to go2_a
  5. For "patrol entire floor" → go2_a takes A+B, go2_b takes C+D

Respond ONLY with valid JSON. No markdown, no backticks, no explanation.

Format:
{
  "tasks": [
    {
      "robot": "go2_a",
      "task": "PATROL",
      "priority": 1,
      "params": {"zone": "A", "speed": "normal"}
    }
  ],
  "confidence": 0.95,
  "reasoning": "one sentence"
}"""


# ─── Decomposer class ────────────────────────────────────────────────────────

class TaskDecomposer:
    def __init__(self):
        token_path = Path(__file__).parents[3] / ".groq_token"
        api_key = token_path.read_text().strip()
        self.client = AsyncGroq(api_key=api_key)
        self.model  = "llama-3.1-8b-instant"

    async def decompose(self, goal: str) -> DecompositionResult:
        logger.info(f"Decomposing: '{goal}'")
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": f"Decompose: {goal}"},
                ],
                temperature=0.1,
                max_tokens=512,
            )
            raw  = resp.choices[0].message.content.strip()
            data = json.loads(raw)
            tasks = [TaskItem(**t) for t in data["tasks"]]
            return DecompositionResult(
                tasks=tasks,
                raw_goal=goal,
                confidence=float(data.get("confidence", 0.8)),
                reasoning=data.get("reasoning", ""),
            )
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}")
            return self._fallback(goal)
        except Exception as e:
            logger.error(f"Decompose error: {e}")
            raise

    def _fallback(self, goal: str) -> DecompositionResult:
        logger.warning("Using fallback decomposition")
        return DecompositionResult(
            tasks=[
                TaskItem(robot="go2_a", task="PATROL", priority=1,
                         params={"zone": "A", "speed": "normal"}),
                TaskItem(robot="go2_b", task="PATROL", priority=1,
                         params={"zone": "C", "speed": "normal"}),
            ],
            raw_goal=goal,
            confidence=0.3,
            reasoning="Fallback: LLM unavailable",
        )


_decomposer: TaskDecomposer | None = None

def get_decomposer() -> TaskDecomposer:
    global _decomposer
    if _decomposer is None:
        _decomposer = TaskDecomposer()
    return _decomposer
