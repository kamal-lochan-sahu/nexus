import aiosqlite
import asyncio
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "nexus.db"

CREATE_ROBOT_STATE = """
CREATE TABLE IF NOT EXISTS robot_state (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    robot_id    TEXT    NOT NULL DEFAULT 'go2_001',
    timestamp   REAL    NOT NULL,
    pos_x       REAL    DEFAULT 0.0,
    pos_y       REAL    DEFAULT 0.0,
    pos_z       REAL    DEFAULT 0.0,
    heading_deg REAL    DEFAULT 0.0,
    velocity    REAL    DEFAULT 0.0,
    gait        TEXT    DEFAULT 'stand',
    mode        TEXT    DEFAULT 'idle'
);
"""

CREATE_JOINT_HEALTH = """
CREATE TABLE IF NOT EXISTS joint_health (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    robot_id     TEXT    NOT NULL DEFAULT 'go2_001',
    timestamp    REAL    NOT NULL,
    joint_name   TEXT    NOT NULL,
    health_pct   REAL    DEFAULT 100.0,
    temperature  REAL    DEFAULT 25.0,
    vibration    REAL    DEFAULT 0.0,
    current_a    REAL    DEFAULT 0.0,
    wear_rate    REAL    DEFAULT 0.0
);
"""

CREATE_TWIN_FORECAST = """
CREATE TABLE IF NOT EXISTS twin_forecast (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    robot_id      TEXT    NOT NULL DEFAULT 'go2_001',
    timestamp     REAL    NOT NULL,
    joint_name    TEXT    NOT NULL,
    fail_in_hours REAL    DEFAULT 999.0,
    confidence    REAL    DEFAULT 0.0,
    severity      TEXT    DEFAULT 'ok',
    action        TEXT    DEFAULT 'none',
    acknowledged  INTEGER DEFAULT 0
);
"""

CREATE_COMMAND_LOG = """
CREATE TABLE IF NOT EXISTS command_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      REAL    NOT NULL,
    robot_id       TEXT    NOT NULL DEFAULT 'go2_001',
    input_text     TEXT    NOT NULL,
    module_used    TEXT    DEFAULT 'unknown',
    intent         TEXT    DEFAULT 'unknown',
    confidence     REAL    DEFAULT 0.0,
    status         TEXT    DEFAULT 'pending',
    blocked_by     TEXT    DEFAULT NULL,
    blocked_reason TEXT    DEFAULT NULL
);
"""

CREATE_SAFETY_EVENTS = """
CREATE TABLE IF NOT EXISTS safety_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    REAL    NOT NULL,
    event_type   TEXT    NOT NULL,
    zone         TEXT    DEFAULT 'unknown',
    distance_m   REAL    DEFAULT 0.0,
    human_intent TEXT    DEFAULT 'unknown',
    speed_before REAL    DEFAULT 0.0,
    speed_after  REAL    DEFAULT 0.0,
    duration_ms  INTEGER DEFAULT 0
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_joint_health_ts  ON joint_health(robot_id, timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_robot_state_ts   ON robot_state(robot_id, timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_twin_forecast_ts ON twin_forecast(robot_id, timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_command_log_ts   ON command_log(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_safety_events_ts ON safety_events(timestamp);",
]

ALL_TABLES = [
    CREATE_ROBOT_STATE,
    CREATE_JOINT_HEALTH,
    CREATE_TWIN_FORECAST,
    CREATE_COMMAND_LOG,
    CREATE_SAFETY_EVENTS,
]

async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        for table_sql in ALL_TABLES:
            await db.execute(table_sql)
        for index_sql in CREATE_INDEXES:
            await db.execute(index_sql)
        await db.commit()
    print(f"[DB] Initialized at: {DB_PATH}")

async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db
