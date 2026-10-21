"""
groq_config.py - one place for everything the Groq users share: API key, model, request options,
error wording and JSON extraction. Used by nl2rc (llm_engine), flexcell (task_decomposer) and
embodied_gpt (vla_engine), so a retired model or a missing key is fixed in one spot.
"""
import json
import os
import re
from pathlib import Path
from typing import Optional

# Groq retired llama-3.1-8b-instant on 2026-08-16; its recommended replacement is gpt-oss-20b.
# Override with the GROQ_MODEL environment variable (see https://console.groq.com/docs/models).
DEFAULT_MODEL = "openai/gpt-oss-20b"
RETIRED_MODELS = {
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
}
REQUEST_TIMEOUT_SECONDS = 10.0

# Local-development fallback: a git-ignored file in the repo root (see .gitignore).
KEY_FILE = Path(__file__).resolve().parents[2] / ".groq_token"

MISSING_KEY_ERROR = ("GROQ_API_KEY is not set. Set the environment variable, "
                     "or put the key in .groq_token in the repo root for local development.")


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


def get_model() -> str:
    """GROQ_MODEL from the environment (retired ids are mapped to their replacement)."""
    model = os.environ.get("GROQ_MODEL", "").strip() or DEFAULT_MODEL
    return RETIRED_MODELS.get(model, model)


def request_options(model: str, max_tokens: int = 300) -> dict:
    """gpt-oss models reason before answering and the reasoning counts against the token limit:
    keep it short and leave room for the answer. Other models use the classic limit."""
    if model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": "low", "max_completion_tokens": max(1024, max_tokens)}
    return {"max_tokens": max_tokens}


def is_model_unavailable(message: str) -> bool:
    lowered = message.lower()
    return "model_not_found" in lowered or "decommission" in lowered


def describe_api_error(error: Exception, model: str) -> str:
    """Turn an API exception into a message that says what to do."""
    message = str(error)
    if is_model_unavailable(message):
        return (f"Groq model '{model}' is unavailable (retired or no access). "
                "Set GROQ_MODEL to a current model: https://console.groq.com/docs/deprecations")
    return f"Groq API error: {message}"


def extract_json_object(text: str) -> Optional[dict]:
    """The first JSON object in `text` (also inside ``` fences or surrounding prose), else None."""
    if not isinstance(text, str):
        return None
    candidate = text.strip()
    for attempt in (candidate, None):
        if attempt is None:
            match = re.search(r"\{.*\}", candidate, re.DOTALL)
            if not match:
                return None
            attempt = match.group()
        try:
            parsed = json.loads(attempt)
        except json.JSONDecodeError:
            continue
        return parsed if isinstance(parsed, dict) else None
    return None
