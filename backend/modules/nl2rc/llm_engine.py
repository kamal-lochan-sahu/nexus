"""
llm_engine.py — Groq API client (Llama-3.1-8b)
Natural language → structured JSON robot command
"""
import asyncio
import json
import os
import re
from pathlib import Path
from typing import Optional

# ── Config ────────────────────────────────────────────────────────
# Groq retired llama-3.1-8b-instant on 2026-08-16; its recommended replacement is gpt-oss-20b.
# Override with the GROQ_MODEL environment variable (see https://console.groq.com/docs/models).
DEFAULT_MODEL = "openai/gpt-oss-20b"
RETIRED_MODELS = {
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
}
REQUEST_TIMEOUT_SECONDS = 10.0
# Local-development fallback: a git-ignored file in the repo root (see .gitignore).
KEY_FILE = Path(__file__).resolve().parents[3] / ".groq_token"

MISSING_KEY_ERROR = ("GROQ_API_KEY is not set. Set the environment variable, "
                     "or put the key in .groq_token in the repo root for local development.")

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


# ── Model selection ───────────────────────────────────────────────
def get_model() -> str:
    """GROQ_MODEL from the environment (retired ids are mapped to their replacement)."""
    model = os.environ.get("GROQ_MODEL", "").strip() or DEFAULT_MODEL
    return RETIRED_MODELS.get(model, model)


def request_options(model: str) -> dict:
    """gpt-oss models reason before answering and the reasoning counts against the token limit:
    keep it short and leave room for the JSON. Other models use the classic limit."""
    if model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": "low", "max_completion_tokens": 1024}
    return {"max_tokens": 300}


def _model_unavailable(message: str) -> bool:
    lowered = message.lower()
    return "model_not_found" in lowered or "decommission" in lowered


# ── API key and client ────────────────────────────────────────────
def get_api_key() -> str:
    """GROQ_API_KEY from the environment, else the first line of KEY_FILE. '' if neither."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        return key
    try:
        lines = KEY_FILE.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return ""
    if not lines:
        return ""
    line = lines[0].strip()
    if "=" in line:                      # also accept a "GROQ_API_KEY=..." style file
        line = line.split("=", 1)[1]
    return line.strip().strip("'\"")


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
    Groq API call karo — Llama-3.1-8b.
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
        message = str(e)
        if _model_unavailable(message):
            return {"error": f"Groq model '{model}' is unavailable (retired or no access). "
                             "Set GROQ_MODEL to a current model: https://console.groq.com/docs/deprecations"}
        return {"error": f"Groq API error: {message}"}


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
