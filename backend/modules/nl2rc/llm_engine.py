"""
llm_engine.py — Groq API client (Llama-3.1-8b)
Natural language → structured JSON robot command
"""
import json
import os
import re

from groq import Groq

# ── Config ────────────────────────────────────────────────────────
GROQ_KEY = open(os.path.expanduser("~/projects/nexus/.groq_token")).read().strip()
MODEL    = "llama-3.1-8b-instant"
client   = Groq(api_key=GROQ_KEY)

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


# ── Main function ─────────────────────────────────────────────────
async def call_llm(user_input: str) -> dict:
    """
    Groq API call karo — Llama-3.1-8b.
    Returns parsed JSON dict ya error dict.
    """
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_input},
            ],
            max_tokens=300,
            temperature=0.1,
        )

        generated_text = response.choices[0].message.content
        return _extract_json(generated_text, user_input)

    except Exception as e:
        return {"error": f"Groq API error: {str(e)}"}


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
