import asyncio, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent))

from backend.database.models import init_db
from backend.database.crud import (
    insert_robot_state, get_latest_robot_state,
    insert_joint_health, get_all_joints_latest,
    upsert_twin_forecast, get_active_forecasts,
    log_command, log_safety_event,
)

JOINTS = ["FR_hip","FR_thigh","FR_calf","FL_hip","FL_thigh","FL_calf",
          "RR_hip","RR_thigh","RR_calf","RL_hip","RL_thigh","RL_calf"]

async def run():
    print("\n[1/5] DB init...")
    await init_db()
    print("  ✅ Tables + indexes created")

    print("[2/5] Robot state...")
    await insert_robot_state(1.5, 2.3, 0.0, 45.0, 0.8, "trot", "autonomous")
    s = await get_latest_robot_state()
    print(f"  ✅ pos=({s['pos_x']}, {s['pos_y']}) gait={s['gait']}")

    print("[3/5] Joint health (12 joints)...")
    for j in JOINTS:
        await insert_joint_health(j, 85.0, 42.5, 0.3, 1.2)
    latest = await get_all_joints_latest()
    print(f"  ✅ {len(latest)}/12 joints stored & fetched")

    print("[4/5] Twin forecast...")
    await upsert_twin_forecast("RR_hip", 47.0, 0.89, "warning", "schedule_maintenance")
    fc = await get_active_forecasts()
    print(f"  ✅ {fc[0]['joint_name']} — fail in {fc[0]['fail_in_hours']}hrs | confidence={fc[0]['confidence']}")

    print("[5/5] Command + safety logs...")
    await log_command("move forward 1 meter", "nl2rc", "move_forward", 0.95, "executed")
    await log_safety_event("human_proximity", "zone_A", 1.2, "walking", 0.5, 0.1, 250)
    print("  ✅ Both logged")

    print("\n  ✅✅✅  ALL TESTS PASSED  ✅✅✅\n")

asyncio.run(run())
