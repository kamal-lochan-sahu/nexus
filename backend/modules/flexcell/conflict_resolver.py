"""
FlexCell — Step 3: Conflict Resolver
Proximity check every 500ms — <1.5m → pause lower priority robot
"""

import asyncio
import logging
import math
import time
from typing import Optional

from .fleet_scheduler import FleetScheduler, RobotStatus

logger = logging.getLogger(__name__)

PAUSE_DISTANCE  = 1.5   # meters — pause if closer than this
RESUME_DISTANCE = 2.0   # meters — resume when separation exceeds this


class ConflictResolver:
    def __init__(self, scheduler: FleetScheduler):
        self.scheduler  = scheduler
        self._running   = False
        self._task: Optional[asyncio.Task] = None
        self._conflicts: list[dict] = []

    def _distance(self, pos_a: dict, pos_b: dict) -> float:
        dx = pos_a["x"] - pos_b["x"]
        dy = pos_a["y"] - pos_b["y"]
        return math.sqrt(dx*dx + dy*dy)

    async def _check_loop(self) -> None:
        while self._running:
            await asyncio.sleep(0.5)
            await self._check()

    async def _check(self) -> None:
        state_a = self.scheduler.get_robot_state("go2_a")
        state_b = self.scheduler.get_robot_state("go2_b")

        dist = self._distance(state_a.position, state_b.position)

        # Both active → check for conflict
        if (state_a.status == RobotStatus.ACTIVE and
                state_b.status == RobotStatus.ACTIVE):

            if dist < PAUSE_DISTANCE:
                # Compare task priorities — higher number = lower priority
                prio_a = state_a.current_task.priority if state_a.current_task else 5
                prio_b = state_b.current_task.priority if state_b.current_task else 5

                if prio_a >= prio_b:
                    # go2_a lower priority → pause go2_a
                    self.scheduler.pause_robot(
                        "go2_a",
                        f"proximity to go2_b at {dist:.2f}m"
                    )
                    self._log_conflict("go2_a", "go2_b", dist)
                else:
                    # go2_b lower priority → pause go2_b
                    self.scheduler.pause_robot(
                        "go2_b",
                        f"proximity to go2_a at {dist:.2f}m"
                    )
                    self._log_conflict("go2_b", "go2_a", dist)

        # One paused → check if safe to resume
        for paused, other in [("go2_a", "go2_b"), ("go2_b", "go2_a")]:
            s_paused = self.scheduler.get_robot_state(paused)
            if s_paused.status == RobotStatus.PAUSED:
                if dist > RESUME_DISTANCE:
                    self.scheduler.resume_robot(paused)
                    logger.info(
                        f"{paused} resumed — separation {dist:.2f}m > {RESUME_DISTANCE}m"
                    )

    def _log_conflict(self, paused: str, active: str, dist: float) -> None:
        event = {
            "timestamp": time.time(),
            "paused":    paused,
            "active":    active,
            "distance":  round(dist, 3),
        }
        self._conflicts.append(event)
        logger.warning(
            f"CONFLICT: {paused} paused — {dist:.2f}m from {active}"
        )

    def get_conflicts(self) -> list[dict]:
        return list(self._conflicts)

    async def start(self) -> None:
        self._running = True
        self._task    = asyncio.create_task(self._check_loop())
        logger.info("ConflictResolver started (500ms polling)")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()


_resolver: ConflictResolver | None = None

def get_resolver() -> ConflictResolver:
    global _resolver
    if _resolver is None:
        from .fleet_scheduler import get_scheduler
        _resolver = ConflictResolver(get_scheduler())
    return _resolver
