"""
FlexCell — Step 2: Fleet Scheduler
asyncio priority queue — assigns tasks to robots, syncs status every 500ms
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from .task_decomposer import TaskItem

logger = logging.getLogger(__name__)


class RobotStatus(str, Enum):
    IDLE    = "idle"
    ACTIVE  = "active"
    PAUSED  = "paused"
    STOPPED = "stopped"
    CHARGING= "charging"


@dataclass
class RobotState:
    robot_id:   str
    status:     RobotStatus  = RobotStatus.IDLE
    current_task: Optional[TaskItem] = None
    position:   dict         = field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    battery:    float        = 100.0   # percent
    speed:      float        = 0.0     # m/s
    last_update:float        = field(default_factory=time.time)


@dataclass(order=True)
class PrioritizedTask:
    priority: int
    seq:      int            # tiebreaker — FIFO within same priority
    task:     TaskItem       = field(compare=False)


class FleetScheduler:
    def __init__(self):
        self._queues: dict[str, asyncio.PriorityQueue] = {
            "go2_a": asyncio.PriorityQueue(),
            "go2_b": asyncio.PriorityQueue(),
        }
        self._states: dict[str, RobotState] = {
            "go2_a": RobotState(robot_id="go2_a"),
            "go2_b": RobotState(robot_id="go2_b"),
        }
        self._seq       = 0
        self._running   = False
        self._sync_task: Optional[asyncio.Task] = None
        self._coord_log: list[dict] = []    # coordination events

    # ── Public API ───────────────────────────────────────────────────────────

    async def enqueue_tasks(self, tasks: list[TaskItem]) -> None:
        """Add list of tasks from decomposer into robot queues."""
        for t in tasks:
            self._seq += 1
            pt = PrioritizedTask(priority=t.priority, seq=self._seq, task=t)
            await self._queues[t.robot].put(pt)
            logger.info(f"Queued [{t.robot}] {t.task} p={t.priority}")

    async def next_task(self, robot_id: str) -> Optional[TaskItem]:
        """Robot polls for its next task (non-blocking)."""
        q = self._queues[robot_id]
        try:
            pt: PrioritizedTask = q.get_nowait()
            self._states[robot_id].current_task = pt.task
            self._states[robot_id].status = RobotStatus.ACTIVE
            return pt.task
        except asyncio.QueueEmpty:
            return None

    def update_position(self, robot_id: str, x: float, y: float) -> None:
        s = self._states[robot_id]
        s.position   = {"x": round(x, 3), "y": round(y, 3)}
        s.last_update = time.time()

    def pause_robot(self, robot_id: str, reason: str = "") -> None:
        self._states[robot_id].status = RobotStatus.PAUSED
        self._log_event(robot_id, "PAUSED", reason)
        logger.warning(f"{robot_id} PAUSED: {reason}")

    def resume_robot(self, robot_id: str) -> None:
        s = self._states[robot_id]
        if s.status == RobotStatus.PAUSED:
            s.status = RobotStatus.ACTIVE
            self._log_event(robot_id, "RESUMED", "")
            logger.info(f"{robot_id} RESUMED")

    def stop_robot(self, robot_id: str) -> None:
        self._states[robot_id].status = RobotStatus.STOPPED
        self._log_event(robot_id, "STOPPED", "manual")

    def get_fleet_status(self) -> dict:
        pending = sum(q.qsize() for q in self._queues.values())
        active  = sum(
            1 for s in self._states.values()
            if s.status == RobotStatus.ACTIVE
        )
        return {
            "tasks_active":         active,
            "tasks_pending":        pending,
            "coordination_events":  len(self._coord_log),
            "go2_a_task": self._task_name("go2_a"),
            "go2_b_task": self._task_name("go2_b"),
            "go2_a_status": self._states["go2_a"].status.value,
            "go2_b_status": self._states["go2_b"].status.value,
            "go2_a_position": self._states["go2_a"].position,
            "go2_b_position": self._states["go2_b"].position,
        }

    def get_coord_log(self) -> list[dict]:
        return list(self._coord_log)

    def get_robot_state(self, robot_id: str) -> RobotState:
        return self._states[robot_id]

    # ── Internal ─────────────────────────────────────────────────────────────

    def _task_name(self, robot_id: str) -> str:
        t = self._states[robot_id].current_task
        if t is None:
            return "idle"
        zone = t.params.get("zone", "")
        return f"{t.task.lower()}_zone_{zone}".strip("_")

    def _log_event(self, robot_id: str, event: str, detail: str) -> None:
        import time
        self._coord_log.append({
            "timestamp": time.time(),
            "robot":     robot_id,
            "event":     event,
            "detail":    detail,
        })
        # Keep last 200 events
        if len(self._coord_log) > 200:
            self._coord_log.pop(0)

    async def _status_sync_loop(self) -> None:
        """Sync every 500ms — called by start()."""
        while self._running:
            await asyncio.sleep(0.5)
            for robot_id, state in self._states.items():
                if state.status == RobotStatus.ACTIVE:
                    if state.current_task is None:
                        next_t = await self.next_task(robot_id)
                        if next_t:
                            logger.info(f"{robot_id} picked up: {next_t.task}")

    async def start(self) -> None:
        self._running   = True
        self._sync_task = asyncio.create_task(self._status_sync_loop())
        logger.info("FleetScheduler started")

    async def stop(self) -> None:
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
        logger.info("FleetScheduler stopped")


_scheduler: FleetScheduler | None = None

def get_scheduler() -> FleetScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = FleetScheduler()
    return _scheduler
