"""Tests for core.groq_config (shared by nl2rc, flexcell and embodied_gpt)."""
import pytest

from core import groq_config as gc


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.setattr(gc, "KEY_FILE", tmp_path / "missing.token")
    return monkeypatch, tmp_path


def key_file(env, content):
    monkeypatch, tmp = env
    path = tmp / ".groq_token"
    path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(gc, "KEY_FILE", path)


# ── API key ───────────────────────────────────────────────────────

def test_no_key_anywhere_gives_empty_string(env):
    assert gc.get_api_key() == ""


def test_key_from_environment_is_stripped(env):
    env[0].setenv("GROQ_API_KEY", "  gsk_env  ")
    assert gc.get_api_key() == "gsk_env"


def test_key_file_is_used_when_no_environment_key(env):
    key_file(env, "gsk_file\n\n")
    assert gc.get_api_key() == "gsk_file"


def test_environment_key_wins_over_key_file(env):
    key_file(env, "gsk_file")
    env[0].setenv("GROQ_API_KEY", "gsk_env")
    assert gc.get_api_key() == "gsk_env"


def test_blank_environment_key_falls_through_to_the_file(env):
    key_file(env, "gsk_file")
    env[0].setenv("GROQ_API_KEY", "   ")
    assert gc.get_api_key() == "gsk_file"


@pytest.mark.parametrize("content", ["", "\n", "   \n\n"])
def test_empty_key_file_counts_as_missing(env, content):
    key_file(env, content)
    assert gc.get_api_key() == ""


@pytest.mark.parametrize("content", ['GROQ_API_KEY=gsk_q', 'GROQ_API_KEY="gsk_q"', "  gsk_q  ", "gsk_q\nsecond line"])
def test_key_file_formats(env, content):
    key_file(env, content)
    assert gc.get_api_key() == "gsk_q"


def test_key_file_points_at_the_repo_root():
    assert gc.KEY_FILE.name == ".groq_token"
    assert (gc.KEY_FILE.parent / "backend").is_dir()


# ── model ─────────────────────────────────────────────────────────

def test_default_model_is_the_groq_recommended_replacement(env):
    assert gc.get_model() == "openai/gpt-oss-20b"


def test_model_can_be_overridden(env):
    env[0].setenv("GROQ_MODEL", " some-vendor/some-model ")
    assert gc.get_model() == "some-vendor/some-model"


@pytest.mark.parametrize("retired,replacement", [
    ("llama-3.1-8b-instant", "openai/gpt-oss-20b"),
    ("llama-3.3-70b-versatile", "openai/gpt-oss-120b"),
])
def test_retired_model_ids_are_mapped_to_their_replacement(env, retired, replacement):
    env[0].setenv("GROQ_MODEL", retired)
    assert gc.get_model() == replacement


def test_blank_model_variable_falls_back_to_the_default(env):
    env[0].setenv("GROQ_MODEL", "   ")
    assert gc.get_model() == gc.DEFAULT_MODEL


# ── request options ───────────────────────────────────────────────

def test_gpt_oss_keeps_reasoning_short_and_leaves_room_for_the_answer():
    options = gc.request_options("openai/gpt-oss-20b")
    assert options == {"reasoning_effort": "low", "max_completion_tokens": 1024}
    assert gc.request_options("openai/gpt-oss-120b", max_tokens=2000)["max_completion_tokens"] == 2000


def test_other_models_use_the_classic_token_limit():
    assert gc.request_options("some-vendor/some-model") == {"max_tokens": 300}
    assert gc.request_options("some-vendor/some-model", max_tokens=512) == {"max_tokens": 512}


# ── error wording ─────────────────────────────────────────────────

@pytest.mark.parametrize("message", [
    "Error code: 404 - {'error': {'code': 'model_not_found'}}",
    "The model has been DECOMMISSIONED",
])
def test_unavailable_model_gets_an_actionable_error(message):
    text = gc.describe_api_error(RuntimeError(message), "openai/gpt-oss-20b")
    assert "openai/gpt-oss-20b" in text and "GROQ_MODEL" in text and "deprecations" in text
    assert not text.startswith("Groq API error")


def test_other_errors_keep_their_message():
    assert gc.describe_api_error(RuntimeError("boom"), "m") == "Groq API error: boom"


# ── JSON extraction ───────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    '{"a": 1}',
    '  {"a": 1}\n',
    '```json\n{"a": 1}\n```',
    'Sure, here you go:\n{"a": 1}\nHope that helps!',
])
def test_json_object_is_found_in_common_shapes(text):
    assert gc.extract_json_object(text) == {"a": 1}


@pytest.mark.parametrize("text", ["no json here", "", "   ", "{not valid}", "[1, 2, 3]", None, 42])
def test_no_usable_object_gives_none(text):
    assert gc.extract_json_object(text) is None
