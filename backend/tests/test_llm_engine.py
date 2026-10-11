"""Tests for modules.nl2rc.llm_engine (no network: the Groq client is replaced by a fake)."""
import asyncio
import json
import time
from types import SimpleNamespace

import pytest

from modules.nl2rc import llm_engine as le

GOOD_JSON = json.dumps({"intent": "walk", "plan": [{"step": 1, "action": "walk", "params": {}}], "confidence": 0.9})


def fake_client(content=GOOD_JSON, exc=None, delay=0.0, calls=None, finish_reason="stop"):
    def create(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        if delay:
            time.sleep(delay)
        if exc:
            raise exc
        choice = SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)
        return SimpleNamespace(choices=[choice])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


@pytest.fixture
def env(monkeypatch, tmp_path):
    """No key in the environment and no key file, plus a recorder for the key the client receives."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.setattr(le, "KEY_FILE", tmp_path / "missing.token")
    seen = {"keys": [], "calls": []}

    def get_client(key):
        seen["keys"].append(key)
        return fake_client(calls=seen["calls"])

    monkeypatch.setattr(le, "_get_client", get_client)
    return SimpleNamespace(seen=seen, tmp=tmp_path, monkeypatch=monkeypatch)


def call(text="walk forward"):
    return asyncio.run(le.call_llm(text))


# ── key handling ──────────────────────────────────────────────────

def test_missing_key_gives_a_clear_error_and_never_builds_a_client(env):
    result = call()
    assert "GROQ_API_KEY" in result["error"] and "Connection" not in result["error"]
    assert env.seen["keys"] == []


def test_key_from_environment_is_stripped_and_used(env):
    env.monkeypatch.setenv("GROQ_API_KEY", "  gsk_env  ")
    assert call()["intent"] == "walk"
    assert env.seen["keys"] == ["gsk_env"]


def test_key_file_is_used_when_no_environment_key(env):
    key_file = env.tmp / ".groq_token"
    key_file.write_text("gsk_file\n\n", encoding="utf-8")
    env.monkeypatch.setattr(le, "KEY_FILE", key_file)
    call()
    assert env.seen["keys"] == ["gsk_file"]


@pytest.mark.parametrize("content", ['GROQ_API_KEY=gsk_q', 'GROQ_API_KEY="gsk_q"', "  gsk_q  ", "gsk_q\nsecond line"])
def test_key_file_formats(env, content):
    key_file = env.tmp / ".groq_token"
    key_file.write_text(content, encoding="utf-8")
    env.monkeypatch.setattr(le, "KEY_FILE", key_file)
    assert le.get_api_key() == "gsk_q"


def test_environment_key_wins_over_key_file(env):
    key_file = env.tmp / ".groq_token"
    key_file.write_text("gsk_file", encoding="utf-8")
    env.monkeypatch.setattr(le, "KEY_FILE", key_file)
    env.monkeypatch.setenv("GROQ_API_KEY", "gsk_env")
    call()
    assert env.seen["keys"] == ["gsk_env"]


def test_blank_environment_key_falls_through_to_the_file(env):
    key_file = env.tmp / ".groq_token"
    key_file.write_text("gsk_file", encoding="utf-8")
    env.monkeypatch.setattr(le, "KEY_FILE", key_file)
    env.monkeypatch.setenv("GROQ_API_KEY", "   ")
    call()
    assert env.seen["keys"] == ["gsk_file"]


def test_empty_key_file_counts_as_missing(env):
    key_file = env.tmp / ".groq_token"
    key_file.write_text("\n", encoding="utf-8")
    env.monkeypatch.setattr(le, "KEY_FILE", key_file)
    assert "GROQ_API_KEY" in call()["error"]


def test_key_file_points_at_the_repo_root():
    assert le.KEY_FILE.name == ".groq_token"
    assert (le.KEY_FILE.parent / "backend").is_dir()


# ── the call itself ───────────────────────────────────────────────

def test_request_uses_the_model_prompt_and_low_temperature(env):
    env.monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    call("turn left")
    request = env.seen["calls"][0]
    assert request["model"] == "openai/gpt-oss-20b" and request["temperature"] == 0.1
    assert request["messages"][0] == {"role": "system", "content": le.SYSTEM_PROMPT}
    assert request["messages"][1] == {"role": "user", "content": "turn left"}


def test_success_adds_original_input_and_module(env):
    env.monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    result = call("walk forward")
    assert result["original_input"] == "walk forward" and result["module_used"] == "nl2rc"


def test_api_error_is_reported_without_raising(env):
    env.monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    env.monkeypatch.setattr(le, "_get_client", lambda key: fake_client(exc=RuntimeError("boom")))
    assert call()["error"] == "Groq API error: boom"


@pytest.mark.parametrize("content,expected", [
    ("I cannot do that", "No JSON in response"),
    (None, "LLM returned no text"),
    ("   ", "LLM returned no text"),
    ("{not valid json}", "JSON parse failed"),
])
def test_bad_model_output_is_reported(env, content, expected):
    env.monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    env.monkeypatch.setattr(le, "_get_client", lambda key: fake_client(content=content))
    assert expected in call()["error"]


def test_json_is_found_inside_surrounding_text(env):
    env.monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    env.monkeypatch.setattr(le, "_get_client", lambda key: fake_client(content=f"Sure!\n{GOOD_JSON}\nDone."))
    assert call()["intent"] == "walk"


def test_slow_api_call_does_not_block_the_event_loop(env):
    env.monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    env.monkeypatch.setattr(le, "_get_client", lambda key: fake_client(delay=0.4))

    async def scenario():
        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.05)
                ticks += 1

        task = asyncio.create_task(ticker())
        result = await le.call_llm("walk forward")
        task.cancel()
        return result, ticks

    result, ticks = asyncio.run(scenario())
    assert result["intent"] == "walk" and ticks >= 4   # the loop kept running during the 0.4 s call


# ── model selection and request options ──────────────────────────

def test_default_model_is_the_groq_recommended_replacement(env):
    assert le.get_model() == "openai/gpt-oss-20b"


def test_gpt_oss_request_keeps_reasoning_short_and_leaves_room_for_the_answer(env):
    env.monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    call()
    request = env.seen["calls"][0]
    assert request["reasoning_effort"] == "low" and request["max_completion_tokens"] == 1024
    assert "max_tokens" not in request


def test_other_models_use_the_classic_token_limit(env):
    env.monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    env.monkeypatch.setenv("GROQ_MODEL", "some-vendor/some-model")
    call()
    request = env.seen["calls"][0]
    assert request["model"] == "some-vendor/some-model"
    assert request["max_tokens"] == 300 and "reasoning_effort" not in request


@pytest.mark.parametrize("retired,replacement", [
    ("llama-3.1-8b-instant", "openai/gpt-oss-20b"),
    ("llama-3.3-70b-versatile", "openai/gpt-oss-120b"),
])
def test_retired_model_ids_are_mapped_to_their_replacement(env, retired, replacement):
    env.monkeypatch.setenv("GROQ_MODEL", retired)
    assert le.get_model() == replacement


def test_blank_model_variable_falls_back_to_the_default(env):
    env.monkeypatch.setenv("GROQ_MODEL", "   ")
    assert le.get_model() == le.DEFAULT_MODEL


@pytest.mark.parametrize("message", [
    "Error code: 404 - {'error': {'code': 'model_not_found'}}",
    "The model has been decommissioned",
])
def test_unavailable_model_gets_an_actionable_error(env, message):
    env.monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    env.monkeypatch.setattr(le, "_get_client", lambda key: fake_client(exc=RuntimeError(message)))
    error = call()["error"]
    assert "openai/gpt-oss-20b" in error and "GROQ_MODEL" in error and "deprecations" in error
    assert not error.startswith("Groq API error")


def test_out_of_tokens_is_explained(env):
    env.monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    env.monkeypatch.setattr(le, "_get_client", lambda key: fake_client(content="", finish_reason="length"))
    error = call()["error"]
    assert "finish_reason=length" in error and "token limit" in error
