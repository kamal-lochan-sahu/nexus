"""
FlexCell Phase 5 — End-to-end test (MODE B, no ROS2)
Run: python test_flexcell.py
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

from modules.flexcell.task_decomposer import get_decomposer
from modules.flexcell.fleet_scheduler import get_scheduler
from modules.flexcell.conflict_resolver import get_resolver

DIV = "=" * 56

TEST_GOALS = [
    "Patrol entire factory floor",
    "Inspect zone B and guard zone D",
    "Both robots return to charge immediately",
]


async def test_decomposer():
    print("")
    print(DIV)
    print("TEST 1: Task Decomposer")
    print(DIV)
    decomposer = get_decomposer()

    for goal in TEST_GOALS:
        print("")
        print("GOAL: " + goal)
        result = await decomposer.decompose(goal)
        print("  Confidence : " + str(round(result.confidence, 2)))
        print("  Reasoning  : " + str(result.reasoning))
        print("  Tasks (" + str(len(result.tasks)) + "):")
        for t in result.tasks:
            print("    [" + t.robot + "] " + t.task + " | p=" + str(t.priority) + " | " + str(t.params))
    return True


async def test_scheduler():
    print("")
    print(DIV)
    print("TEST 2: Fleet Scheduler")
    print(DIV)

    decomposer = get_decomposer()
    scheduler  = get_scheduler()
    await scheduler.start()

    result = await decomposer.decompose("Patrol entire factory floor")
    await scheduler.enqueue_tasks(result.tasks)

    task_a = await scheduler.next_task("go2_a")
    task_b = await scheduler.next_task("go2_b")

    print("  Go2-A task : " + (task_a.task + " " + str(task_a.params) if task_a else "None"))
    print("  Go2-B task : " + (task_b.task + " " + str(task_b.params) if task_b else "None"))

    status = scheduler.get_fleet_status()
    print("")
    print("  Fleet status:")
    for k, v in status.items():
        print("    " + str(k) + ": " + str(v))

    await scheduler.stop()
    return task_a is not None and task_b is not None


async def test_conflict():
    print("")
    print(DIV)
    print("TEST 3: Conflict Resolver")
    print(DIV)

    scheduler = get_scheduler()
    resolver  = get_resolver()
    await scheduler.start()

    from modules.flexcell.task_decomposer import TaskItem
    from modules.flexcell.fleet_scheduler import RobotStatus

    task_a = TaskItem(robot="go2_a", task="PATROL", priority=1, params={"zone": "A"})
    task_b = TaskItem(robot="go2_b", task="PATROL", priority=2, params={"zone": "C"})
    scheduler._states["go2_a"].current_task = task_a
    scheduler._states["go2_a"].status = RobotStatus.ACTIVE
    scheduler._states["go2_b"].current_task = task_b
    scheduler._states["go2_b"].status = RobotStatus.ACTIVE

    scheduler.update_position("go2_a", 0.0, 0.0)
    scheduler.update_position("go2_b", 0.5, 0.5)
    print("  Proximity conflict (0.71m) — checking...")
    await resolver._check()

    paused = [rid for rid, s in scheduler._states.items() if s.status == RobotStatus.PAUSED]
    print("  Paused: " + str(paused))
    print("  Conflicts logged: " + str(len(resolver.get_conflicts())))

    scheduler.update_position("go2_a", 0.0, 0.0)
    scheduler.update_position("go2_b", 2.5, 2.5)
    print("  Separation (3.5m) — checking resume...")
    await resolver._check()

    active = [rid for rid, s in scheduler._states.items() if s.status == RobotStatus.ACTIVE]
    print("  Active: " + str(active))

    await scheduler.stop()
    return len(paused) > 0


async def main():
    print("")
    print("NEXUS Phase 5 — FlexCell Test Suite")
    print(DIV)

    results = {}

    try:
        results["decomposer"] = await test_decomposer()
    except Exception as e:
        print("  ERROR: " + str(e))
        results["decomposer"] = False

    try:
        results["scheduler"] = await test_scheduler()
    except Exception as e:
        print("  ERROR: " + str(e))
        results["scheduler"] = False

    try:
        results["conflict_resolver"] = await test_conflict()
    except Exception as e:
        print("  ERROR: " + str(e))
        results["conflict_resolver"] = False

    print("")
    print(DIV)
    print("RESULTS")
    print(DIV)
    all_pass = True
    for name, passed in results.items():
        mark = "PASS" if passed else "FAIL"
        print("  [" + mark + "] " + name)
        if not passed:
            all_pass = False

    print(DIV)
    if all_pass:
        print("ALL TESTS PASSED — Phase 5 backend ready.")
    else:
        print("Some tests failed. Fix before proceeding.")
    print("")


if __name__ == "__main__":
    asyncio.run(main())
