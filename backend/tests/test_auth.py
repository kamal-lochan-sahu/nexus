"""Tests for core.auth and where it is applied."""
import re
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from core.auth import auth_enabled, require_api_key
from modules.flexcell.flexcell_router import router
from modules.flexcell.fleet_scheduler import get_scheduler

BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def no_key_by_default(monkeypatch):
    monkeypatch.delenv("NEXUS_API_KEY", raising=False)


def small_app():
    app = FastAPI()

    @app.post("/secret", dependencies=[Depends(require_api_key)])
    async def secret():
        return {"ok": True}

    @app.get("/open")
    async def open_route():
        return {"ok": True}

    return TestClient(app)


# ── the dependency ────────────────────────────────────────────────

def test_auth_is_off_when_no_key_is_configured():
    assert auth_enabled() is False
    assert small_app().post("/secret").status_code == 200


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_key_counts_as_not_configured(monkeypatch, blank):
    monkeypatch.setenv("NEXUS_API_KEY", blank)
    assert auth_enabled() is False and small_app().post("/secret").status_code == 200


def test_missing_header_is_rejected(monkeypatch):
    monkeypatch.setenv("NEXUS_API_KEY", "s3cret")
    response = small_app().post("/secret")
    assert response.status_code == 401 and response.headers["www-authenticate"] == "ApiKey"


@pytest.mark.parametrize("sent", ["wrong", "s3cre", "s3cret-extra", "S3CRET", ""])
def test_wrong_key_is_rejected(monkeypatch, sent):
    monkeypatch.setenv("NEXUS_API_KEY", "s3cret")
    assert small_app().post("/secret", headers={"X-API-Key": sent}).status_code == 401


def test_correct_key_is_accepted(monkeypatch):
    monkeypatch.setenv("NEXUS_API_KEY", "s3cret")
    assert small_app().post("/secret", headers={"X-API-Key": "s3cret"}).status_code == 200


def test_padding_around_the_configured_key_is_ignored(monkeypatch):
    monkeypatch.setenv("NEXUS_API_KEY", "  s3cret \n")
    assert small_app().post("/secret", headers={"X-API-Key": "s3cret"}).status_code == 200


def test_non_ascii_key_does_not_crash(monkeypatch):
    monkeypatch.setenv("NEXUS_API_KEY", "s3cret")
    response = small_app().post("/secret", headers={"X-API-Key": "caf\u00e9".encode("latin-1")})
    assert response.status_code == 401


def test_read_only_route_stays_open_even_with_a_key(monkeypatch):
    monkeypatch.setenv("NEXUS_API_KEY", "s3cret")
    assert small_app().get("/open").status_code == 200


def test_key_is_read_at_request_time(monkeypatch):
    client = small_app()
    assert client.post("/secret").status_code == 200
    monkeypatch.setenv("NEXUS_API_KEY", "s3cret")
    assert client.post("/secret").status_code == 401


# ── FlexCell router ───────────────────────────────────────────────

def flexcell_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


PROTECTED = [
    ("/flexcell/task", {"json": {"goal": "patrol"}}),
    ("/flexcell/robot/go2_a/pause", {}),
    ("/flexcell/robot/go2_a/resume", {}),
    ("/flexcell/robot/go2_a/stop", {}),
]


@pytest.mark.parametrize("path,kwargs", PROTECTED)
def test_flexcell_mutations_need_the_key(monkeypatch, path, kwargs):
    monkeypatch.setenv("NEXUS_API_KEY", "s3cret")
    client = flexcell_client()
    assert client.post(path, **kwargs).status_code == 401
    assert client.post(path, headers={"X-API-Key": "nope"}, **kwargs).status_code == 401


def test_flexcell_reads_stay_open(monkeypatch):
    monkeypatch.setenv("NEXUS_API_KEY", "s3cret")
    client = flexcell_client()
    assert client.get("/flexcell/status").status_code == 200
    assert client.get("/flexcell/log").status_code == 200


def test_flexcell_pause_works_with_the_key_and_without_auth(monkeypatch):
    client = flexcell_client()
    try:
        assert client.post("/flexcell/robot/go2_a/pause").status_code == 200       # auth off
        monkeypatch.setenv("NEXUS_API_KEY", "s3cret")
        assert client.post("/flexcell/robot/go2_a/resume", headers={"X-API-Key": "s3cret"}).status_code == 200
    finally:
        get_scheduler().resume_robot("go2_a")


# ── wiring in main.py (text check: importing main needs the heavy modules) ──

def test_main_protects_the_command_endpoint():
    source = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert re.search(r'@app\.post\("/command", dependencies=\[Depends\(require_api_key\)\]\)', source)
    assert "from core.auth import require_api_key" in source


def test_main_warns_when_auth_is_off():
    source = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert "NEXUS_API_KEY is not set" in source
