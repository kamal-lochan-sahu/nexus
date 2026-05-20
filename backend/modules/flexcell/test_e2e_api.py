"""
FlexCell — End-to-end API test
Tests FastAPI endpoints directly (no Gazebo needed)
Run: python test_e2e_api.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from httpx import AsyncClient, ASGITransport


async def main():
    # Import app after path setup
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "main", Path(__file__).parents[2] / "main.py"
    )

    print("\nFlexCell E2E API Test")
    print("=" * 50)

    # Direct module test (avoids full app startup)
    from modules.flexcell.task_decomposer import get_decomposer
    from modules.flexcell.fleet_scheduler import get_scheduler
    from modules.flexcell.flexcell_router import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:

        # Test 1: POST /flexcell/task
        print("\n[1] POST /flexcell/task")
        r = await client.post("/flexcell/task", json={"goal": "Patrol entire factory floor"})
        print(f"    Status  : {r.status_code}")
        data = r.json()
        print(f"    Tasks   : {len(data.get('tasks', []))}")
        for t in data.get("tasks", []):
            print(f"      [{t['robot']}] {t['task']} zone={t['params'].get('zone','?')}")
        print(f"    Reasoning: {data.get('reasoning','')}")

        # Test 2: GET /flexcell/status
        print("\n[2] GET /flexcell/status")
        r = await client.get("/flexcell/status")
        print(f"    Status  : {r.status_code}")
        s = r.json()
        print(f"    Active  : {s.get('tasks_active')}")
        print(f"    Go2-A   : {s.get('go2_a_task')} ({s.get('go2_a_status')})")
        print(f"    Go2-B   : {s.get('go2_b_task')} ({s.get('go2_b_status')})")

        # Test 3: Pause + resume
        print("\n[3] Robot pause/resume")
        r = await client.post("/flexcell/robot/go2_a/pause")
        print(f"    Pause go2_a : {r.json().get('status')}")
        r = await client.post("/flexcell/robot/go2_a/resume")
        print(f"    Resume go2_a: {r.json().get('status')}")

        # Test 4: GET /flexcell/log
        print("\n[4] GET /flexcell/log")
        r = await client.get("/flexcell/log")
        log = r.json()
        print(f"    Coord events: {len(log.get('coord_log', []))}")

        # Test 5: Empty goal → 422
        print("\n[5] Empty goal → expect 400")
        r = await client.post("/flexcell/task", json={"goal": ""})
        print(f"    Status: {r.status_code} (expected 400)")

    print("\n" + "=" * 50)
    print("E2E API tests complete.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
