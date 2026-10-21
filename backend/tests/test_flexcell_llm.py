"""Tests for the FlexCell task decomposer (shared Groq config) and how /flexcell/task reports LLM trouble."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import groq_config as gc
from modules.flexcell import flexcell_router as fr
from modules.flexcell.fleet_scheduler import FleetScheduler
from modules.flexcell.task_decomposer import (
    DecompositionResult, LLMUnavailableError, TaskDecomposer, TaskItem,
)

GOOD = {
    "tasks": [
        {"robot": "go2_a", "task": "patrol", "priority": 1, "params": {"zone": "A"}},
        {"robot": "go2_b", "task": "INSPECT", "priority": 2, "params": {"zone": "D"}},
    ],
    "confidence": 0.9,
    "reasoning": "split the floor",
}


def fake_async_client(content=None, exc=None, calls=None, finish_reason="stop"):
    content = json.dumps(GOOD) if content is None else content

    async def create(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        if exc:
            raise exc
        choice = SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)
        return SimpleNamespace(choices=[choice])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.delenv("NEXUS_API_KEY", raising=False)
    monkeypatch.setattr(gc, "KEY_FILE", tmp_path / "missing.token")


def decomposer_with(monkeypatch, client, key="gsk_x"):
    if key:
        monkeypatch.setenv("GROQ_API_KEY", key)
    decomposer = TaskDecomposer()
    monkeypatch.setattr(decomposer, "_get_client", lambda _key: client)
    return decomposer


def decompose(decomposer, goal="patrol the floor"):
    return asyncio.run(decomposer.decompose(goal))


# ── decomposer ────────────────────────────────────────────────────

def test_valid_answer_becomes_tasks(monkeypatch):
    result = decompose(decomposer_with(monkeypatch, fake_async_client()))
    assert [t.robot for t in result.tasks] == ["go2_a", "go2_b"]
    assert result.tasks[0].task == "PATROL" and result.confidence == 0.9


@pytest.mark.parametrize("wrapper", ["```json\n{body}\n```", "Here is the plan:\n{body}\nDone."])
def test_json_inside_fences_or_prose_is_accepted(monkeypatch, wrapper):
    content = wrapper.replace("{body}", json.dumps(GOOD))
    result = decompose(decomposer_with(monkeypatch, fake_async_client(content=content)))
    assert len(result.tasks) == 2 and result.confidence == 0.9


@pytest.mark.parametrize("content", [
    "I cannot plan that",
    "{not valid json}",
    json.dumps({"confidence": 0.9}),
    json.dumps({"tasks": "nope"}),
    json.dumps({"tasks": [{"robot": "go2_z", "task": "PATROL", "priority": 1, "params": {}}]}),
    json.dumps({"tasks": [{"robot": "go2_a", "task": "DANCE", "priority": 1, "params": {}}]}),
])
def test_unusable_answer_falls_back_with_low_confidence(monkeypatch, content):
    result = decompose(decomposer_with(monkeypatch, fake_async_client(content=content)))
    assert result.confidence == 0.3 and result.reasoning.startswith("Fallback")


def test_missing_key_is_a_clear_error_and_no_client_is_built(monkeypatch):
    decomposer = TaskDecomposer()
    monkeypatch.setattr(decomposer, "_get_client", lambda _key: pytest.fail("client must not be built"))
    with pytest.raises(LLMUnavailableError, match="GROQ_API_KEY"):
        decompose(decomposer)


def test_api_error_becomes_llm_unavailable_with_the_original_as_cause(monkeypatch):
    boom = RuntimeError("boom")
    with pytest.raises(LLMUnavailableError, match="Groq API error: boom") as info:
        decompose(decomposer_with(monkeypatch, fake_async_client(exc=boom)))
    assert info.value.__cause__ is boom


def test_retired_model_gets_an_actionable_message(monkeypatch):
    client = fake_async_client(exc=RuntimeError("Error code: 404 - {'error': {'code': 'model_not_found'}}"))
    with pytest.raises(LLMUnavailableError) as info:
        decompose(decomposer_with(monkeypatch, client))
    assert "openai/gpt-oss-20b" in str(info.value) and "GROQ_MODEL" in str(info.value)


def test_empty_answer_is_reported_with_the_finish_reason(monkeypatch):
    client = fake_async_client(content="", finish_reason="length")
    with pytest.raises(LLMUnavailableError, match="finish_reason=length"):
        decompose(decomposer_with(monkeypatch, client))


def test_request_uses_the_shared_model_and_options(monkeypatch):
    calls = []
    decompose(decomposer_with(monkeypatch, fake_async_client(calls=calls)), "patrol zone A")
    request = calls[0]
    assert request["model"] == "openai/gpt-oss-20b" and request["temperature"] == 0.1
    assert request["reasoning_effort"] == "low" and request["max_completion_tokens"] == 1024
    assert "max_tokens" not in request and request["messages"][1]["content"] == "Decompose: patrol zone A"


def test_model_property_follows_the_environment(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "some-vendor/some-model")
    assert TaskDecomposer().model == "some-vendor/some-model"


def test_key_can_come_from_the_key_file(monkeypatch, tmp_path):
    key_file = tmp_path / ".groq_token"
    key_file.write_text("gsk_file", encoding="utf-8")
    monkeypatch.setattr(gc, "KEY_FILE", key_file)
    seen = []
    decomposer = TaskDecomposer()
    monkeypatch.setattr(decomposer, "_get_client", lambda key: seen.append(key) or fake_async_client())
    decompose(decomposer)
    assert seen == ["gsk_file"]


# ── POST /flexcell/task ───────────────────────────────────────────

class FakeDecomposer:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    async def decompose(self, goal):
        if self.error:
            raise self.error
        return self.result


def task_client(monkeypatch, decomposer):
    scheduler = FleetScheduler()
    monkeypatch.setattr(fr, "get_decomposer", lambda: decomposer)
    monkeypatch.setattr(fr, "get_scheduler", lambda: scheduler)
    app = FastAPI()
    app.include_router(fr.router)
    return TestClient(app), scheduler


def test_llm_trouble_gives_503_with_the_reason_and_queues_nothing(monkeypatch):
    error = LLMUnavailableError("GROQ_API_KEY is not set. Set the environment variable.")
    client, scheduler = task_client(monkeypatch, FakeDecomposer(error=error))
    response = client.post("/flexcell/task", json={"goal": "patrol the floor"})
    assert response.status_code == 503 and "GROQ_API_KEY" in response.json()["detail"]
    assert scheduler.get_fleet_status()["tasks_pending"] == 0


def test_good_decomposition_is_accepted_and_queued(monkeypatch):
    result = DecompositionResult(
        tasks=[TaskItem(robot="go2_a", task="PATROL", priority=1, params={"zone": "A"}),
               TaskItem(robot="go2_b", task="PATROL", priority=1, params={"zone": "C"})],
        raw_goal="patrol", confidence=0.9, reasoning="split")
    client, scheduler = task_client(monkeypatch, FakeDecomposer(result=result))
    response = client.post("/flexcell/task", json={"goal": "patrol the floor"})
    assert response.status_code == 200 and response.json()["status"] == "accepted"
    assert scheduler.get_fleet_status()["tasks_pending"] == 2


def test_empty_goal_is_still_a_400(monkeypatch):
    client, _ = task_client(monkeypatch, FakeDecomposer(error=AssertionError("must not be called")))
    assert client.post("/flexcell/task", json={"goal": "   "}).status_code == 400
