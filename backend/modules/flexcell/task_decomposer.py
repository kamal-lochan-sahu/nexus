import os
"""
FlexCell — Step 1: Task Decomposer
High-level goal → structured JSON task list via Groq LLM
"""

import json
import logging
from pathlib import Path
from typing import Optional

from core.groq_config import (
    MISSING_KEY_ERROR,
    REQUEST_TIMEOUT_SECONDS,
    describe_api_error,
    extract_json_object,
    get_api_key,
    get_model,
    request_options,
)
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

class LLMUnavailableError(RuntimeError):
    """The LLM could not be used (no key, retired model, network...). The message says what to do."""


class TaskDecomposer:
    def __init__(self):
        self._client = None
        self._client_key = None

    @property
    def model(self) -> str:
        return get_model()

    def _get_client(self, key: str):
        """Create the async Groq client on first use (and again if the key changes)."""
        if self._client is None or self._client_key != key:
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1)
            self._client_key = key
        return self._client

    async def decompose(self, goal: str) -> DecompositionResult:
        logger.info(f"Decomposing: '{goal}'")
        key = get_api_key()
        if not key:
            # An empty key makes the Groq client report a misleading "Connection error".
            raise LLMUnavailableError(MISSING_KEY_ERROR)
        model = get_model()
        try:
            resp = await self._get_client(key).chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": f"Decompose: {goal}"},
                ],
                temperature=0.1,
                **request_options(model, max_tokens=512),
            )
        except Exception as e:
            logger.error(f"Decompose error: {e}")
            raise LLMUnavailableError(describe_api_error(e, model)) from e

        choice = resp.choices[0]
        raw = (choice.message.content or "").strip()
        if not raw:
            raise LLMUnavailableError(
                f"LLM returned no text (finish_reason={getattr(choice, 'finish_reason', None)}). "
                "A reasoning model may have used up its token limit.")

        data = extract_json_object(raw)
        if data is None:
            logger.error("No JSON object in the LLM answer")
            return self._fallback(goal)
        try:
            tasks = [TaskItem(**t) for t in data["tasks"]]
            return DecompositionResult(
                tasks=tasks,
                raw_goal=goal,
                confidence=float(data.get("confidence", 0.8)),
                reasoning=data.get("reasoning", ""),
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Bad task list from the LLM: {e}")
            return self._fallback(goal)

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
