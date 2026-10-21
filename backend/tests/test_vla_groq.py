"""Tests for the Groq step of EmbodiedGPT's VLA engine. CLIP and YOLO are stubbed: only the LLM call is tested."""
import importlib
import json
import sys
import types
from types import SimpleNamespace

import pytest

from core import groq_config as gc

DETECTIONS = [{"label": "pallet_box", "confidence": 0.9}]
PLAN = {"intent": "visual_navigate",
        "plan": [{"step": 1, "action": "navigate", "params": {"target": "pallet_box"}}],
        "confidence": 0.9}


_DEFAULT = object()


def fake_client(content=_DEFAULT, exc=None, calls=None):
    content = json.dumps(PLAN) if content is _DEFAULT else content

    def create(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        if exc:
            raise exc
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


@pytest.fixture
def vla(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "clip_encoder", types.SimpleNamespace(CLIPEncoder=object))
    monkeypatch.setitem(sys.modules, "yolo_detector", types.SimpleNamespace(YOLODetector=object))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.setattr(gc, "KEY_FILE", tmp_path / "missing.token")
    sys.modules.pop("modules.embodied_gpt.vla_engine", None)
    module = importlib.import_module("modules.embodied_gpt.vla_engine")
    yield module
    sys.modules.pop("modules.embodied_gpt.vla_engine", None)


def run(vla, command="go to the box"):
    engine = vla.VLAEngine.__new__(vla.VLAEngine)      # skip __init__: it would load CLIP and YOLO
    return engine._groq_call(command, DETECTIONS, "a warehouse", 0.5, True)


def is_fallback(result):
    return result["plan"][0]["action"] == "navigate" and result["safety_check"] == "clear" and "visual_context" in result


def test_missing_key_uses_the_fallback_without_building_a_client(vla, monkeypatch):
    monkeypatch.setattr(vla, "_get_groq_client", lambda key: pytest.fail("client must not be built"))
    assert is_fallback(run(vla))


def test_success_uses_the_shared_model_and_options(vla, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    calls = []
    monkeypatch.setattr(vla, "_get_groq_client", lambda key: fake_client(calls=calls))
    result = run(vla, "go to the box")
    assert result["original_input"] == "go to the box" and result["module_used"] == "embodied_gpt"
    assert result["intent"] == "visual_navigate"
    request = calls[0]
    assert request["model"] == "openai/gpt-oss-20b" and request["temperature"] == 0.1
    assert request["reasoning_effort"] == "low" and request["max_completion_tokens"] == 1024


def test_key_can_come_from_the_key_file(vla, monkeypatch, tmp_path):
    key_file = tmp_path / ".groq_token"
    key_file.write_text("gsk_file", encoding="utf-8")
    monkeypatch.setattr(gc, "KEY_FILE", key_file)
    seen = []
    monkeypatch.setattr(vla, "_get_groq_client", lambda key: seen.append(key) or fake_client())
    run(vla)
    assert seen == ["gsk_file"]


@pytest.mark.parametrize("wrapper", ["```json\n{body}\n```", "Plan:\n{body}\nDone."])
def test_json_inside_fences_or_prose_is_accepted(vla, monkeypatch, wrapper):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    content = wrapper.replace("{body}", json.dumps(PLAN))
    monkeypatch.setattr(vla, "_get_groq_client", lambda key: fake_client(content=content))
    assert run(vla)["intent"] == "visual_navigate"


@pytest.mark.parametrize("content", ["no json at all", "", None, "{broken"])
def test_unusable_answer_falls_back(vla, monkeypatch, content):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    monkeypatch.setattr(vla, "_get_groq_client", lambda key: fake_client(content=content))
    result = run(vla)
    assert is_fallback(result) and "confidence" in result


def test_api_error_falls_back(vla, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    monkeypatch.setattr(vla, "_get_groq_client", lambda key: fake_client(exc=RuntimeError("model_not_found")))
    assert is_fallback(run(vla))


def test_groq_package_missing_falls_back(vla, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    monkeypatch.setattr(vla, "GROQ_OK", False)
    monkeypatch.setattr(vla, "_get_groq_client", lambda key: pytest.fail("client must not be built"))
    assert is_fallback(run(vla))
