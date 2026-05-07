import asyncio
import time
import aiosqlite
from typing import Optional
from .models import DB_PATH

_write_lock = asyncio.Lock()

async def insert_robot_state(pos_x, pos_y, pos_z, heading_deg, velocity,
                              gait="stand", mode="idle", robot_id="go2_001"):
    ts = time.time()
    async with _write_lock:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO robot_state (robot_id,timestamp,pos_x,pos_y,pos_z,heading_deg,velocity,gait,mode) VALUES (?,?,?,?,?,?,?,?,?)",
                (robot_id, ts, pos_x, pos_y, pos_z, heading_deg, velocity, gait, mode),
            )
            await db.commit()

async def get_latest_robot_state(robot_id="go2_001"):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM robot_state WHERE robot_id=? ORDER BY timestamp DESC LIMIT 1", (robot_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def insert_joint_health(joint_name, health_pct, temperature, vibration,
                               current_a, wear_rate=0.0, robot_id="go2_001"):
    ts = time.time()
    async with _write_lock:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO joint_health (robot_id,timestamp,joint_name,health_pct,temperature,vibration,current_a,wear_rate) VALUES (?,?,?,?,?,?,?,?)",
                (robot_id, ts, joint_name, health_pct, temperature, vibration, current_a, wear_rate),
            )
            await db.commit()

async def get_joint_health_window(joint_name, hours=24.0, robot_id="go2_001"):
    since = time.time() - (hours * 3600)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT timestamp,health_pct,temperature,vibration,current_a,wear_rate FROM joint_health WHERE robot_id=? AND joint_name=? AND timestamp>=? ORDER BY timestamp ASC",
            (robot_id, joint_name, since),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def get_all_joints_latest(robot_id="go2_001"):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT jh.* FROM joint_health jh
               INNER JOIN (SELECT joint_name, MAX(timestamp) as max_ts FROM joint_health WHERE robot_id=? GROUP BY joint_name) latest
               ON jh.joint_name=latest.joint_name AND jh.timestamp=latest.max_ts WHERE jh.robot_id=?""",
            (robot_id, robot_id),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def upsert_twin_forecast(joint_name, fail_in_hours, confidence, severity,
                                action="monitor", robot_id="go2_001"):
    ts = time.time()
    async with _write_lock:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO twin_forecast (robot_id,timestamp,joint_name,fail_in_hours,confidence,severity,action,acknowledged) VALUES (?,?,?,?,?,?,?,0)",
                (robot_id, ts, joint_name, fail_in_hours, confidence, severity, action),
            )
            await db.commit()

async def get_active_forecasts(robot_id="go2_001"):
    since = time.time() - (6 * 3600)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM twin_forecast WHERE robot_id=? AND timestamp>=? AND acknowledged=0 ORDER BY confidence DESC",
            (robot_id, since),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def acknowledge_forecast(forecast_id):
    async with _write_lock:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE twin_forecast SET acknowledged=1 WHERE id=?", (forecast_id,))
            await db.commit()

async def log_command(input_text, module_used, intent, confidence, status,
                      blocked_by=None, blocked_reason=None, robot_id="go2_001"):
    ts = time.time()
    async with _write_lock:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO command_log (timestamp,robot_id,input_text,module_used,intent,confidence,status,blocked_by,blocked_reason) VALUES (?,?,?,?,?,?,?,?,?)",
                (ts, robot_id, input_text, module_used, intent, confidence, status, blocked_by, blocked_reason),
            )
            await db.commit()

async def log_safety_event(event_type, zone, distance_m, human_intent,
                            speed_before, speed_after, duration_ms):
    ts = time.time()
    async with _write_lock:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO safety_events (timestamp,event_type,zone,distance_m,human_intent,speed_before,speed_after,duration_ms) VALUES (?,?,?,?,?,?,?,?)",
                (ts, event_type, zone, distance_m, human_intent, speed_before, speed_after, duration_ms),
            )
            await db.commit()

async def batch_flush(
    robot_state_data: dict,
    joints_data: list[dict],
) -> None:
    """
    Single connection mein sab kuch likho.
    robot_state + 12 joints = 1 transaction, 1 commit.
    Replaces 13 separate inserts → ~50ms instead of ~2000ms.
    """
    ts = time.time()
    async with _write_lock:
        async with aiosqlite.connect(DB_PATH) as db:
            # Robot state
            await db.execute(
                "INSERT INTO robot_state (robot_id,timestamp,pos_x,pos_y,pos_z,heading_deg,velocity,gait,mode) VALUES (?,?,?,?,?,?,?,?,?)",
                (robot_state_data["robot_id"], ts,
                 robot_state_data["pos_x"],    robot_state_data["pos_y"],
                 robot_state_data["pos_z"],     robot_state_data["heading_deg"],
                 robot_state_data["velocity"],  robot_state_data["gait"],
                 robot_state_data["mode"]),
            )
            # 12 joints — executemany = single roundtrip
            rows = [
                (j["robot_id"], ts, j["joint_name"], j["health_pct"],
                 j["temperature"], j["vibration"], j["current_a"], j["wear_rate"])
                for j in joints_data
            ]
            await db.executemany(
                "INSERT INTO joint_health (robot_id,timestamp,joint_name,health_pct,temperature,vibration,current_a,wear_rate) VALUES (?,?,?,?,?,?,?,?)",
                rows,
            )
            await db.commit()
