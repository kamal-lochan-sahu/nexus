"""Tests for core.audit, the pipeline's audit hook, the database helpers and the wiring in main.py."""
import asyncio
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core import command_pipeline as cp
from core.audit import record_outcome
from database import crud, models

BACKEND = Path(__file__).resolve().parent.parent


# ── record_outcome ────────────────────────────────────────────────

class Recorder:
    def __init__(self, fail=False):
        self.commands, self.events, self.fail = [], [], fail

    async def log_command(self, *args):
        if self.fail:
            raise RuntimeError("database is locked")
        self.commands.append(args)

    async def log_safety_event(self, *args):
        self.events.append(args)


def record(text, result, recorder=None):
    recorder = recorder or Recorder()
    asyncio.run(record_outcome(text, result, log_command=recorder.log_command,
                               log_safety_event=recorder.log_safety_event))
    return recorder


def test_executed_command_is_logged_with_its_action_and_confidence():
    result = {"status": "executed", "command": {"action": "move_forward", "confidence": 0.95}}
    recorder = record("walk forward 1 meter", result)
    assert recorder.commands == [("walk forward 1 meter", "nl2rc", "move_forward", 0.95, "executed", None, None)]
    assert recorder.events == []


def test_rejected_command_records_who_blocked_it_and_why():
    result = {"status": "rejected", "stage": "safety_pre", "reason": "Unsafe command: keyword 'hit' is not allowed."}
    command = record("hit the wall", result).commands[0]
    assert command[2:] == ("safety_pre", 0.0, "rejected", "safety_pre", "Unsafe command: keyword 'hit' is not allowed.")


def test_not_sent_is_blamed_on_the_bridge():
    result = {"status": "not_sent", "reason": "Validated but not sent: robot bridge is offline.",
              "command": {"action": "move_forward", "confidence": 0.9}}
    command = record("walk forward", result).commands[0]
    assert command[4:] == ("not_sent", "bridge", "Validated but not sent: robot bridge is offline.")


def test_orchestrated_commands_keep_their_module():
    result = {"status": "ok", "stage": "orchestrated", "module": "flexcell"}
    command = record("patrol the floor", result).commands[0]
    assert command[1] == "flexcell" and command[4] == "ok"


def test_emergency_stop_is_a_safety_event_too():
    result = {"status": "stopped", "stage": "emergency", "stopped": ["cmd_vel"]}
    recorder = record("STOP ALL", result)
    assert recorder.commands[0][1:5] == ("emergency", "emergency", 0.0, "stopped")
    assert recorder.events == [("emergency_stop", "n/a", 0.0, "unknown", 0.0, 0.0, 0)]


def test_failed_emergency_stop_is_logged_with_its_note():
    result = {"status": "stop_failed", "stage": "emergency", "note": "Nothing could be stopped."}
    recorder = record("stop", result)
    assert recorder.commands[0][5:] == ("emergency", "Nothing could be stopped.")
    assert recorder.events[0][0] == "emergency_stop"


def test_human_safety_block_is_a_safety_event():
    result = {"status": "blocked", "stage": "human_safety", "reason": "Human in stop zone", "human_safety": "stop"}
    recorder = record("walk forward", result)
    assert recorder.commands[0][5:] == ("human_safety", "Human in stop zone")
    assert recorder.events == [("human_safety_block", "stop", 0.0, "unknown", 0.0, 0.0, 0)]


def test_llm_error_is_logged_as_blocked_by_the_llm_stage():
    result = {"status": "error", "stage": "llm", "reason": "GROQ_API_KEY is not set."}
    assert record("walk", result).commands[0][5:] == ("llm", "GROQ_API_KEY is not set.")


def test_long_text_is_clipped_and_non_text_becomes_empty():
    assert len(record("x" * 2000, {"status": "ok"}).commands[0][0]) == 500
    assert record(None, {"status": "ok"}).commands[0][0] == ""
    assert record(42, {"status": "ok"}).commands[0][0] == ""


def test_odd_confidence_values_become_zero():
    for bad in (float("nan"), "high", None):
        result = {"status": "executed", "command": {"action": "move_forward", "confidence": bad}}
        assert record("walk", result).commands[0][3] == 0.0


def test_non_dict_result_records_nothing():
    assert record("walk", "oops").commands == []


def test_a_failing_database_never_raises():
    assert record("walk", {"status": "ok"}, Recorder(fail=True)).commands == []


# ── the pipeline hook ─────────────────────────────────────────────

class FakeBridge:
    connected = True

    def send_cmd_vel(self, linear_x=0.0, angular_z=0.0, **_):
        return True

    def stop_robot(self, **_):
        return True


class FakeOrch:
    def handle(self, text):
        return {"module": "nl2rc"}

    def stop_all(self):
        pass


async def llm_must_not_run(_text):
    raise AssertionError("LLM must not be called")


def run_command(text, audit=None):
    return asyncio.run(cp.execute_command(text, call_llm=llm_must_not_run, get_orchestrator=lambda: FakeOrch(),
                                          bridge=FakeBridge(), audit=audit))


def test_audit_receives_the_text_and_the_result_and_does_not_change_it():
    seen = []

    async def audit(text, result):
        seen.append((text, dict(result)))

    result = run_command("STOP ALL", audit)
    assert result["status"] == "stopped" and seen == [("STOP ALL", result)]


def test_no_audit_callback_is_fine():
    assert run_command("stop")["status"] == "stopped"


def test_a_failing_audit_does_not_change_the_result():
    async def audit(text, result):
        raise RuntimeError("disk full")

    assert run_command("stop", audit)["status"] == "stopped"


def test_a_slow_audit_is_cut_off(monkeypatch):
    monkeypatch.setattr(cp, "AUDIT_TIMEOUT_SECONDS", 0.05)

    async def audit(text, result):
        await asyncio.sleep(5)

    started = time.monotonic()
    result = run_command("stop", audit)
    assert result["status"] == "stopped"
    assert time.monotonic() - started < 2


def test_rejected_input_is_audited_too():
    seen = []

    async def audit(text, result):
        seen.append(result["status"])

    run_command("hit the wall", audit)
    assert seen == ["rejected"]


# ── database helpers (temporary database file) ────────────────────

@pytest.fixture
def db(monkeypatch, tmp_path):
    path = tmp_path / "nested" / "test.db"
    monkeypatch.setattr(models, "DB_PATH", path)
    monkeypatch.setattr(crud, "DB_PATH", path)
    return path


def test_init_db_creates_the_file_the_folder_and_all_tables(db):
    asyncio.run(models.init_db())
    assert db.is_file()
    import sqlite3
    tables = {row[0] for row in sqlite3.connect(db).execute("select name from sqlite_master where type='table'")}
    assert {"robot_state", "joint_health", "twin_forecast", "command_log", "safety_events"} <= tables


def test_init_db_can_run_twice(db):
    async def twice():
        await models.init_db()
        await crud.log_command("walk", "nl2rc", "move_forward", 0.9, "executed")
        await models.init_db()
        return await crud.get_recent_commands()
    assert len(asyncio.run(twice())) == 1


def test_recent_commands_are_newest_first_and_limited(db):
    async def scenario():
        await models.init_db()
        for index in range(5):
            await crud.log_command(f"command {index}", "nl2rc", "x", 0.5, "executed")
        return await crud.get_recent_commands(3), await crud.get_recent_commands()
    three, everything = asyncio.run(scenario())
    assert [c["input_text"] for c in three] == ["command 4", "command 3", "command 2"]
    assert len(everything) == 5 and three[0]["status"] == "executed" and "blocked_by" in three[0]


def test_outcome_round_trip_through_the_real_database(db):
    async def scenario():
        await models.init_db()
        await record_outcome("STOP ALL", {"status": "stopped", "stage": "emergency"},
                             log_command=crud.log_command, log_safety_event=crud.log_safety_event)
        await record_outcome("hit the wall", {"status": "rejected", "stage": "safety_pre", "reason": "no"},
                             log_command=crud.log_command, log_safety_event=crud.log_safety_event)
        return await crud.get_recent_commands()
    rows = asyncio.run(scenario())
    assert [(r["input_text"], r["status"], r["blocked_by"]) for r in rows] == [
        ("hit the wall", "rejected", "safety_pre"), ("STOP ALL", "stopped", None)]
    import sqlite3
    events = sqlite3.connect(db).execute("select event_type from safety_events").fetchall()
    assert events == [("emergency_stop",)]


def test_database_location_can_be_overridden_by_the_environment(tmp_path):
    code = "from database.models import DB_PATH; print(DB_PATH)"
    custom = tmp_path / "custom.db"
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True,
                         env={**os.environ, "NEXUS_DB_PATH": str(custom)}).stdout.strip()
    assert out == str(custom)
    default = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True,
                             env={k: v for k, v in os.environ.items() if k != "NEXUS_DB_PATH"}).stdout.strip()
    assert default.endswith(os.path.join("data", "nexus.db"))


# ── wiring in main.py (text check: importing main needs the heavy modules) ──

def test_main_initialises_the_database_at_startup():
    source = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert "from backend.database.models import init_db" in source and "await init_db()" in source


def test_main_passes_the_audit_callback_to_the_pipeline():
    source = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert "audit=audit," in source and "record_outcome" in source


def test_recent_commands_endpoint_needs_the_key():
    source = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert re.search(r'@app\.get\("/commands/recent", dependencies=\[Depends\(require_api_key\)\]\)', source)
