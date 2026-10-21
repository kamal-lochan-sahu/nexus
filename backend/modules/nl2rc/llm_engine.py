"""
llm_engine.py — Groq API client
Natural language → structured JSON robot command

Key, model and request options live in core.groq_config (shared with flexcell and embodied_gpt).
"""
import asyncio
import json
import re
from typing import Optional

from core.groq_config import (
    DEFAULT_MODEL,
    KEY_FILE,
    MISSING_KEY_ERROR,
    REQUEST_TIMEOUT_SECONDS,
    describe_api_error,
    get_api_key,
    get_model,
    request_options,
)

# ── System prompt ─────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a robot command parser for a Unitree Go2 quadruped robot.
Convert natural language instructions into JSON commands.
Supported actions: walk, turn, navigate, inspect, sit, stand, stop, status

Respond with ONLY valid JSON, no explanation, no markdown:
{
  "intent": "walk",
  "plan": [
    {
      "step": 1,
      "action": "walk",
      "params": {
        "direction": "forward",
        "distance": 2.0,
        "velocity": 0.3,
        "gait": "trot",
        "unit": "meters"
      }
    }
  ],
  "confidence": 0.95,
  "clarification_needed": null
}

Safety limits — never exceed:
- max velocity: 0.5 m/s
- max distance: 5.0 m
- max rotation: 180 degrees"""


# ── Client ────────────────────────────────────────────────────────
_client = None
_client_key: Optional[str] = None


def _get_client(key: str):
    """Create the Groq client on first use (and again if the key changes)."""
    global _client, _client_key
    if _client is None or _client_key != key:
        from groq import Groq
        _client = Groq(api_key=key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1)
        _client_key = key
    return _client


# ── Main function ─────────────────────────────────────────────────
async def call_llm(user_input: str) -> dict:
    """
    Groq API call karo.
    Returns parsed JSON dict ya error dict.
    """
    key = get_api_key()
    if not key:
        # An empty key makes the Groq client fail with a misleading "Connection error",
        # so say what is actually wrong.
        return {"error": MISSING_KEY_ERROR}

    model = get_model()
    try:
        client = _get_client(key)
        # The Groq client is synchronous: run it in a thread so the event loop stays free.
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_input},
            ],
            temperature=0.1,
            **request_options(model),
        )
        choice = response.choices[0]
        generated_text = choice.message.content or ""
        if not generated_text.strip():
            reason = getattr(choice, "finish_reason", None)
            return {"error": f"LLM returned no text (finish_reason={reason}). "
                             "A reasoning model may have used up its token limit."}
        return _extract_json(generated_text, user_input)

    except Exception as e:
        return {"error": describe_api_error(e, model)}


def _extract_json(text: str, original_input: str) -> dict:
    """Generated text se JSON extract karo."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        return {
            "error": "No JSON in response",
            "raw": text[:300],
        }
    try:
        parsed = json.loads(match.group())
        parsed["original_input"] = original_input
        parsed["module_used"]    = "nl2rc"
        return parsed
    except json.JSONDecodeError as e:
        return {
            "error": f"JSON parse failed: {e}",
            "raw": text[:300],
        }
