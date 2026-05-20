#!/usr/bin/env python3
"""
NEXUS Phase 5 — FlexCell Setup Script
Run from: ~/projects/nexus/
Command : python setup_phase5_flexcell.py
"""

import os
import sys
from pathlib import Path

# ─── Root detection ──────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
if not (ROOT / "backend").exists():
    print("ERROR: Run this script from ~/projects/nexus/")
    sys.exit(1)

# ─── File definitions ────────────────────────────────────────────────────────

FILES = {}

# ════════════════════════════════════════════════════════════════════════════
# 1. backend/modules/flexcell/__init__.py
# ════════════════════════════════════════════════════════════════════════════
FILES["backend/modules/flexcell/__init__.py"] = '''\
# FlexCell — Multi-robot coordination module
from .task_decomposer import TaskDecomposer, get_decomposer
from .fleet_scheduler import FleetScheduler, get_scheduler
from .conflict_resolver import ConflictResolver, get_resolver

__all__ = [
    "TaskDecomposer", "get_decomposer",
    "FleetScheduler",  "get_scheduler",
    "ConflictResolver","get_resolver",
]
'''

# ════════════════════════════════════════════════════════════════════════════
# 2. task_decomposer.py
# ════════════════════════════════════════════════════════════════════════════
FILES["backend/modules/flexcell/task_decomposer.py"] = '''\
"""
FlexCell — Step 1: Task Decomposer
High-level goal → structured JSON task list via Groq LLM
"""

import json
import logging
from pathlib import Path
from typing import Optional

from groq import AsyncGroq
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

# ─── Models ─────────────────────────────────────────────────────────────────

class TaskItem(BaseModel):
    robot:    str   # "go2_a" | "go2_b"
    task:     str   # PATROL | INSPECT | ESCORT | GUARD | CHARGE
    priority: int   # 1 = highest, 5 = lowest
    params:   dict  # zone, speed, target, etc.

    @field_validator("robot")
    @classmethod
    def validate_robot(cls, v):
        if v not in ("go2_a", "go2_b"):
            raise ValueError(f"Invalid robot: {v}")
        return v

    @field_validator("task")
    @classmethod
    def validate_task(cls, v):
        allowed = {"PATROL", "INSPECT", "ESCORT", "GUARD", "CHARGE"}
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"Invalid task: {v}. Allowed: {allowed}")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        if not (1 <= v <= 5):
            raise ValueError(f"Priority must be 1-5, got {v}")
        return v


class DecompositionResult(BaseModel):
    tasks:      list[TaskItem]
    raw_goal:   str
    confidence: float
    reasoning:  Optional[str] = None


# ─── System prompt ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a multi-robot task planner for a factory floor.

You have TWO robots: go2_a and go2_b.

ZONES (6x6m arena):
  Zone A: top-left     x[-3,0],  y[0,+3]
  Zone B: top-right    x[0,+3],  y[0,+3]
  Zone C: bottom-left  x[-3,0],  y[-3,0]
  Zone D: bottom-right x[0,+3],  y[-3,0]

TASK TYPES:
  PATROL  - systematically cover an area
  INSPECT - check a specific location once
  ESCORT  - follow a human safely
  GUARD   - hold position in a zone
  CHARGE  - return robot to charging dock

RULES:
  1. Distribute work evenly between go2_a and go2_b
  2. Never assign both robots to the exact same zone simultaneously
  3. Priority 1 = most urgent, 5 = least urgent
  4. If task needs only one robot, assign to go2_a
  5. For "patrol entire floor" → go2_a takes A+B, go2_b takes C+D

Respond ONLY with valid JSON. No markdown, no backticks, no explanation.

Format:
{
  "tasks": [
    {
      "robot": "go2_a",
      "task": "PATROL",
      "priority": 1,
      "params": {"zone": "A", "speed": "normal"}
    }
  ],
  "confidence": 0.95,
  "reasoning": "one sentence"
}"""


# ─── Decomposer class ────────────────────────────────────────────────────────

class TaskDecomposer:
    def __init__(self):
        token_path = Path(__file__).parents[3] / ".groq_token"
        api_key = token_path.read_text().strip()
        self.client = AsyncGroq(api_key=api_key)
        self.model  = "llama-3.1-8b-instant"

    async def decompose(self, goal: str) -> DecompositionResult:
        logger.info(f"Decomposing: \'{goal}\'")
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": f"Decompose: {goal}"},
                ],
                temperature=0.1,
                max_tokens=512,
            )
            raw  = resp.choices[0].message.content.strip()
            data = json.loads(raw)
            tasks = [TaskItem(**t) for t in data["tasks"]]
            return DecompositionResult(
                tasks=tasks,
                raw_goal=goal,
                confidence=float(data.get("confidence", 0.8)),
                reasoning=data.get("reasoning", ""),
            )
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}")
            return self._fallback(goal)
        except Exception as e:
            logger.error(f"Decompose error: {e}")
            raise

    def _fallback(self, goal: str) -> DecompositionResult:
        logger.warning("Using fallback decomposition")
        return DecompositionResult(
            tasks=[
                TaskItem(robot="go2_a", task="PATROL", priority=1,
                         params={"zone": "A", "speed": "normal"}),
                TaskItem(robot="go2_b", task="PATROL", priority=1,
                         params={"zone": "C", "speed": "normal"}),
            ],
            raw_goal=goal,
            confidence=0.3,
            reasoning="Fallback: LLM unavailable",
        )


_decomposer: TaskDecomposer | None = None

def get_decomposer() -> TaskDecomposer:
    global _decomposer
    if _decomposer is None:
        _decomposer = TaskDecomposer()
    return _decomposer
'''

# ════════════════════════════════════════════════════════════════════════════
# 3. fleet_scheduler.py
# ════════════════════════════════════════════════════════════════════════════
FILES["backend/modules/flexcell/fleet_scheduler.py"] = '''\
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
'''

# ════════════════════════════════════════════════════════════════════════════
# 4. conflict_resolver.py
# ════════════════════════════════════════════════════════════════════════════
FILES["backend/modules/flexcell/conflict_resolver.py"] = '''\
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
'''

# ════════════════════════════════════════════════════════════════════════════
# 5. flexcell_router.py
# ════════════════════════════════════════════════════════════════════════════
FILES["backend/modules/flexcell/flexcell_router.py"] = '''\
"""
FlexCell — Step 6: FastAPI Router
POST /flexcell/task   → decompose + enqueue
GET  /flexcell/status → fleet dashboard data
GET  /flexcell/log    → coordination event log
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .task_decomposer import get_decomposer
from .fleet_scheduler  import get_scheduler
from .conflict_resolver import get_resolver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/flexcell", tags=["FlexCell"])


class TaskRequest(BaseModel):
    goal: str


class TaskResponse(BaseModel):
    status:    str
    tasks:     list[dict]
    reasoning: str
    confidence: float


@router.post("/task", response_model=TaskResponse)
async def submit_task(req: TaskRequest):
    """
    POST /flexcell/task
    Body: {"goal": "Patrol entire factory floor"}
    """
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="goal cannot be empty")

    decomposer = get_decomposer()
    scheduler  = get_scheduler()

    result = await decomposer.decompose(req.goal)
    await scheduler.enqueue_tasks(result.tasks)

    logger.info(f"FlexCell task accepted: {len(result.tasks)} subtasks")
    return TaskResponse(
        status    = "accepted",
        tasks     = [t.model_dump() for t in result.tasks],
        reasoning = result.reasoning or "",
        confidence= result.confidence,
    )


@router.get("/status")
async def get_status():
    """GET /flexcell/status — for WebSocket broadcast + dashboard."""
    scheduler = get_scheduler()
    return scheduler.get_fleet_status()


@router.get("/log")
async def get_log():
    """GET /flexcell/log — coordination events."""
    resolver = get_resolver()
    scheduler = get_scheduler()
    return {
        "conflict_events": resolver.get_conflicts(),
        "coord_log":       scheduler.get_coord_log(),
    }


@router.post("/robot/{robot_id}/pause")
async def pause_robot(robot_id: str):
    if robot_id not in ("go2_a", "go2_b"):
        raise HTTPException(status_code=400, detail="Invalid robot_id")
    get_scheduler().pause_robot(robot_id, "manual pause")
    return {"status": "paused", "robot": robot_id}


@router.post("/robot/{robot_id}/resume")
async def resume_robot(robot_id: str):
    if robot_id not in ("go2_a", "go2_b"):
        raise HTTPException(status_code=400, detail="Invalid robot_id")
    get_scheduler().resume_robot(robot_id)
    return {"status": "resumed", "robot": robot_id}


@router.post("/robot/{robot_id}/stop")
async def stop_robot(robot_id: str):
    if robot_id not in ("go2_a", "go2_b"):
        raise HTTPException(status_code=400, detail="Invalid robot_id")
    get_scheduler().stop_robot(robot_id)
    return {"status": "stopped", "robot": robot_id}
'''

# ════════════════════════════════════════════════════════════════════════════
# 6. fleet_node.py (ROS2)
# ════════════════════════════════════════════════════════════════════════════
FILES["ros2_ws/src/nexus_robot/nexus_robot/fleet_node.py"] = '''\
"""
FlexCell — Step 4: Fleet ROS2 Node
Manages Go2-A and Go2-B via separate namespaces.
/go2_a/cmd_vel + /go2_b/cmd_vel
/go2_a/odom   + /go2_b/odom
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import math


ZONE_WAYPOINTS = {
    "A": [(-2.5, 2.5), (-1.5, 2.5), (-0.5, 2.5),
          (-2.5, 1.5), (-1.5, 1.5), (-0.5, 1.5)],
    "B": [(0.5, 2.5),  (1.5, 2.5),  (2.5, 2.5),
          (0.5, 1.5),  (1.5, 1.5),  (2.5, 1.5)],
    "C": [(-2.5,-0.5), (-1.5,-0.5), (-0.5,-0.5),
          (-2.5,-1.5), (-1.5,-1.5), (-0.5,-1.5)],
    "D": [(0.5,-0.5),  (1.5,-0.5),  (2.5,-0.5),
          (0.5,-1.5),  (1.5,-1.5),  (2.5,-1.5)],
}

PATROL_SPEED  = 0.3   # m/s
TURN_SPEED    = 0.5   # rad/s
GOAL_TOLERANCE= 0.3   # m


class RobotController:
    """Single robot controller — holds its own state."""

    def __init__(self, node: Node, robot_id: str):
        self.node      = node
        self.robot_id  = robot_id
        self.pos_x     = 0.0
        self.pos_y     = 0.0
        self.yaw       = 0.0
        self.paused    = False
        self.waypoints: list[tuple] = []
        self.wp_idx    = 0

        ns = f"/{robot_id}"
        self.cmd_pub = node.create_publisher(Twist, f"{ns}/cmd_vel", 10)
        node.create_subscription(
            Odometry, f"{ns}/odom", self._odom_cb, 10
        )

    def _odom_cb(self, msg: Odometry) -> None:
        self.pos_x = msg.pose.pose.position.x
        self.pos_y = msg.pose.pose.position.y
        # Extract yaw from quaternion
        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.yaw = math.atan2(siny, cosy)

    def set_patrol_zone(self, zone: str) -> None:
        self.waypoints = ZONE_WAYPOINTS.get(zone, [])
        self.wp_idx    = 0
        self.node.get_logger().info(
            f"{self.robot_id}: Patrol zone {zone} — {len(self.waypoints)} waypoints"
        )

    def stop(self) -> None:
        self.cmd_pub.publish(Twist())

    def patrol_step(self) -> None:
        """Called every 100ms by timer."""
        if self.paused or not self.waypoints:
            self.stop()
            return

        if self.wp_idx >= len(self.waypoints):
            self.wp_idx = 0   # Loop patrol

        gx, gy  = self.waypoints[self.wp_idx]
        dx      = gx - self.pos_x
        dy      = gy - self.pos_y
        dist    = math.sqrt(dx*dx + dy*dy)

        if dist < GOAL_TOLERANCE:
            self.wp_idx += 1
            self.stop()
            return

        # Heading toward goal
        target_yaw = math.atan2(dy, dx)
        yaw_err    = target_yaw - self.yaw
        # Normalize to [-pi, pi]
        while yaw_err >  math.pi: yaw_err -= 2*math.pi
        while yaw_err < -math.pi: yaw_err += 2*math.pi

        cmd = Twist()
        if abs(yaw_err) > 0.2:
            cmd.angular.z = TURN_SPEED * (1 if yaw_err > 0 else -1)
        else:
            cmd.linear.x  = PATROL_SPEED
            cmd.angular.z = 0.3 * yaw_err

        self.cmd_pub.publish(cmd)


class FleetNode(Node):
    def __init__(self):
        super().__init__("fleet_node")
        self.get_logger().info("FleetNode starting...")

        self.go2_a = RobotController(self, "go2_a")
        self.go2_b = RobotController(self, "go2_b")

        # Default patrol zones
        self.go2_a.set_patrol_zone("A")
        self.go2_b.set_patrol_zone("C")

        # 100ms control loop
        self.create_timer(0.1, self._control_loop)
        self.get_logger().info("FleetNode ready. Go2-A→ZoneA, Go2-B→ZoneC")

    def _control_loop(self) -> None:
        self.go2_a.patrol_step()
        self.go2_b.patrol_step()


def main(args=None):
    rclpy.init(args=args)
    node = FleetNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.go2_a.stop()
        node.go2_b.stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
'''

# ════════════════════════════════════════════════════════════════════════════
# 7. Frontend — RobotCard.tsx
# ════════════════════════════════════════════════════════════════════════════
FILES["frontend/app/components/fleet/RobotCard.tsx"] = '''\
"use client";

import React from "react";

interface RobotCardProps {
  robotId:  string;       // "go2_a" | "go2_b"
  status:   string;       // "active" | "paused" | "stopped" | "idle"
  task:     string;
  position: { x: number; y: number };
  battery:  number;       // 0-100
  speed:    number;       // m/s
  onCommand?: () => void;
  onPause?:   () => void;
  onStop?:    () => void;
}

const STATUS_COLORS: Record<string, string> = {
  active:   "bg-green-500",
  paused:   "bg-amber-400",
  stopped:  "bg-red-500",
  idle:     "bg-gray-400",
  charging: "bg-blue-400",
};

const STATUS_RING: Record<string, string> = {
  active:  "ring-green-400",
  paused:  "ring-amber-300",
  stopped: "ring-red-400",
  idle:    "ring-gray-400",
};

export default function RobotCard({
  robotId, status, task, position, battery, speed,
  onCommand, onPause, onStop,
}: RobotCardProps) {
  const label      = robotId.replace("_", "-").toUpperCase();
  const dotColor   = STATUS_COLORS[status] ?? "bg-gray-400";
  const ringColor  = STATUS_RING[status]   ?? "ring-gray-300";
  const battColor  = battery > 50 ? "bg-green-500"
                   : battery > 20 ? "bg-amber-400" : "bg-red-500";

  return (
    <div className={`rounded-2xl border border-white/10 bg-white/5
                     backdrop-blur-sm p-4 ring-1 ${ringColor}
                     flex flex-col gap-3 min-w-[220px]`}>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${dotColor} animate-pulse`} />
          <span className="font-bold text-white text-sm">{label}</span>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium
          ${dotColor} text-white/90`}>
          {status.toUpperCase()}
        </span>
      </div>

      {/* Task */}
      <div className="text-xs text-white/60 uppercase tracking-wide">Task</div>
      <div className="text-sm font-mono text-cyan-300 truncate">{task || "—"}</div>

      {/* Position */}
      <div className="grid grid-cols-2 gap-2 text-xs text-white/70">
        <div>
          <span className="text-white/40">X </span>
          {position.x.toFixed(2)}m
        </div>
        <div>
          <span className="text-white/40">Y </span>
          {position.y.toFixed(2)}m
        </div>
        <div>
          <span className="text-white/40">⚡ </span>
          {speed.toFixed(2)} m/s
        </div>
        <div className="flex items-center gap-1">
          <span className="text-white/40">🔋</span>
          <div className="flex-1 bg-white/10 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full ${battColor}`}
              style={{ width: `${battery}%` }}
            />
          </div>
          <span>{battery}%</span>
        </div>
      </div>

      {/* Buttons */}
      <div className="flex gap-2 pt-1">
        <button
          onClick={onCommand}
          className="flex-1 text-xs bg-cyan-600 hover:bg-cyan-500
                     text-white rounded-lg py-1.5 font-medium transition"
        >
          COMMAND
        </button>
        <button
          onClick={onPause}
          className="flex-1 text-xs bg-amber-600 hover:bg-amber-500
                     text-white rounded-lg py-1.5 font-medium transition"
        >
          PAUSE
        </button>
        <button
          onClick={onStop}
          className="flex-1 text-xs bg-red-600 hover:bg-red-500
                     text-white rounded-lg py-1.5 font-medium transition"
        >
          STOP
        </button>
      </div>
    </div>
  );
}
'''

# ════════════════════════════════════════════════════════════════════════════
# 8. Frontend — TaskQueue.tsx
# ════════════════════════════════════════════════════════════════════════════
FILES["frontend/app/components/fleet/TaskQueue.tsx"] = '''\
"use client";

import React from "react";

interface Task {
  robot:    string;
  task:     string;
  priority: number;
  params:   Record<string, string>;
  status?:  "active" | "pending" | "done";
}

interface TaskQueueProps {
  tasks:    Task[];
  pending?: number;
}

const PRIORITY_LABELS: Record<number, { label: string; color: string }> = {
  1: { label: "URGENT",  color: "bg-red-500/20 text-red-300 border-red-500/30" },
  2: { label: "HIGH",    color: "bg-amber-500/20 text-amber-300 border-amber-500/30" },
  3: { label: "NORMAL",  color: "bg-blue-500/20 text-blue-300 border-blue-500/30" },
  4: { label: "LOW",     color: "bg-gray-500/20 text-gray-300 border-gray-500/30" },
  5: { label: "ROUTINE", color: "bg-gray-500/20 text-gray-400 border-gray-500/20" },
};

const ROBOT_COLOR: Record<string, string> = {
  go2_a: "text-cyan-400",
  go2_b: "text-purple-400",
};

export default function TaskQueue({ tasks, pending = 0 }: TaskQueueProps) {
  const active  = tasks.filter(t => t.status === "active");
  const queued  = tasks.filter(t => t.status === "pending");

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5
                    backdrop-blur-sm p-4 flex flex-col gap-3">

      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-bold text-white text-sm">Task Queue</span>
        <div className="flex gap-2 text-xs">
          <span className="bg-green-500/20 text-green-300 border border-green-500/30
                           px-2 py-0.5 rounded-full">
            {active.length} active
          </span>
          <span className="bg-white/10 text-white/60 border border-white/10
                           px-2 py-0.5 rounded-full">
            {queued.length + pending} pending
          </span>
        </div>
      </div>

      {/* Active tasks */}
      {active.length > 0 && (
        <div>
          <div className="text-xs text-white/40 uppercase tracking-wider mb-2">
            Active
          </div>
          {active.map((t, i) => (
            <TaskRow key={i} task={t} />
          ))}
        </div>
      )}

      {/* Pending tasks */}
      {queued.length > 0 && (
        <div>
          <div className="text-xs text-white/40 uppercase tracking-wider mb-2">
            Pending
          </div>
          {queued.map((t, i) => (
            <TaskRow key={i} task={t} />
          ))}
        </div>
      )}

      {tasks.length === 0 && (
        <div className="text-center text-white/30 text-sm py-4">
          No tasks queued
        </div>
      )}
    </div>
  );
}

function TaskRow({ task }: { task: Task }) {
  const prio  = PRIORITY_LABELS[task.priority] ?? PRIORITY_LABELS[3];
  const rColor= ROBOT_COLOR[task.robot] ?? "text-white";
  const zone  = task.params?.zone ?? "";

  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-white/5
                    last:border-0">
      <span className={`text-xs font-mono font-bold ${rColor} w-14 shrink-0`}>
        {task.robot.replace("_", "-").toUpperCase()}
      </span>
      <span className="text-sm text-white/80 flex-1 font-mono">
        {task.task}{zone ? ` / ${zone}` : ""}
      </span>
      <span className={`text-xs px-2 py-0.5 rounded-full border ${prio.color}`}>
        {prio.label}
      </span>
    </div>
  );
}
'''

# ════════════════════════════════════════════════════════════════════════════
# 9. Frontend — CoordLog.tsx
# ════════════════════════════════════════════════════════════════════════════
FILES["frontend/app/components/fleet/CoordLog.tsx"] = '''\
"use client";

import React, { useEffect, useRef } from "react";

interface CoordEvent {
  timestamp: number;
  robot?:    string;
  paused?:   string;
  active?:   string;
  event?:    string;
  detail?:   string;
  distance?: number;
}

interface CoordLogProps {
  events: CoordEvent[];
  maxVisible?: number;
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("en-IN", {
    hour:   "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatEvent(e: CoordEvent): { msg: string; color: string } {
  if (e.paused && e.distance) {
    return {
      msg:   `${e.paused.toUpperCase()} paused — proximity to ${e.active?.toUpperCase()} at ${e.distance.toFixed(2)}m`,
      color: "text-amber-300",
    };
  }
  if (e.event === "RESUMED") {
    return {
      msg:   `${e.robot?.toUpperCase()} resumed`,
      color: "text-green-300",
    };
  }
  if (e.event === "STOPPED") {
    return {
      msg:   `${e.robot?.toUpperCase()} stopped (${e.detail ?? ""})`,
      color: "text-red-300",
    };
  }
  return {
    msg:   `${e.robot?.toUpperCase() ?? "FLEET"} — ${e.event ?? ""} ${e.detail ?? ""}`,
    color: "text-white/60",
  };
}

export default function CoordLog({ events, maxVisible = 50 }: CoordLogProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const visible = events.slice(-maxVisible);

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5
                    backdrop-blur-sm p-4 flex flex-col gap-2">

      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-bold text-white text-sm">Coordination Log</span>
        <span className="text-xs text-white/40">{events.length} events</span>
      </div>

      {/* Log stream */}
      <div className="overflow-y-auto max-h-48 flex flex-col gap-1
                      scrollbar-thin scrollbar-thumb-white/10">
        {visible.length === 0 && (
          <div className="text-white/30 text-xs text-center py-4">
            No coordination events
          </div>
        )}
        {visible.map((e, i) => {
          const { msg, color } = formatEvent(e);
          return (
            <div key={i} className="flex gap-2 text-xs">
              <span className="text-white/30 shrink-0 font-mono w-20">
                {formatTime(e.timestamp)}
              </span>
              <span className={`${color}`}>{msg}</span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
'''

# ════════════════════════════════════════════════════════════════════════════
# 10. Test script (MODE B — no ROS2/Gazebo)
# ════════════════════════════════════════════════════════════════════════════
FILES["backend/modules/flexcell/test_flexcell.py"] = '''\
"""
FlexCell Phase 5 — End-to-end test (MODE B, no ROS2)
Run: python test_flexcell.py
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parents[2]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

from modules.flexcell.task_decomposer  import get_decomposer
from modules.flexcell.fleet_scheduler  import get_scheduler
from modules.flexcell.conflict_resolver import get_resolver


DIVIDER = "=" * 56

TEST_GOALS = [
    "Patrol entire factory floor",
    "Inspect zone B and guard zone D",
    "Both robots return to charge immediately",
    "Escort worker in zone A while patrolling zone C",
]


async def test_decomposer():
    print(f"\n{DIVIDER}")
    print("TEST 1: Task Decomposer")
    print(DIVIDER)
    decomposer = get_decomposer()

    for goal in TEST_GOALS:
        print(f"\nGOAL: {goal}")
        result = await decomposer.decompose(goal)
        print(f"  Confidence : {result.confidence:.2f}")
        print(f"  Reasoning  : {result.reasoning}")
        print(f"  Tasks ({len(result.tasks)}):")
        for t in result.tasks:
            print(f"    [{t.robot}] {t.task} | p={t.priority} | {t.params}")

    return True


async def test_scheduler():
    print(f"\n{DIVIDER}")
    print("TEST 2: Fleet Scheduler")
    print(DIVIDER)

    decomposer = get_decomposer()
    scheduler  = get_scheduler()

    await scheduler.start()

    result = await decomposer.decompose("Patrol entire factory floor")
    await scheduler.enqueue_tasks(result.tasks)

    # Simulate robots picking up tasks
    task_a = await scheduler.next_task("go2_a")
    task_b = await scheduler.next_task("go2_b")

    print(f"  Go2-A task : {task_a.task if task_a else 'None'} {task_a.params if task_a else ''}")
    print(f"  Go2-B task : {task_b.task if task_b else 'None'} {task_b.params if task_b else ''}")

    status = scheduler.get_fleet_status()
    print(f"\n  Fleet status:")
    for k, v in status.items():
        print(f"    {k}: {v}")

    await scheduler.stop()
    return task_a is not None and task_b is not None


async def test_conflict_resolver():
    print(f"\n{DIVIDER}")
    print("TEST 3: Conflict Resolver")
    print(DIVIDER)

    scheduler = get_scheduler()
    resolver  = get_resolver()

    # Restart scheduler for clean state
    await scheduler.start()

    # Assign tasks so both robots are active
    from modules.flexcell.task_decomposer import TaskItem
    from modules.flexcell.fleet_scheduler import RobotStatus

    task_a = TaskItem(robot="go2_a", task="PATROL", priority=1, params={"zone":"A"})
    task_b = TaskItem(robot="go2_b", task="PATROL", priority=2, params={"zone":"C"})
    scheduler._states["go2_a"].current_task = task_a
    scheduler._states["go2_a"].status = RobotStatus.ACTIVE
    scheduler._states["go2_b"].current_task = task_b
    scheduler._states["go2_b"].status = RobotStatus.ACTIVE

    # Simulate robots CLOSE together (< 1.5m) → should pause lower priority
    scheduler.update_position("go2_a", 0.0, 0.0)
    scheduler.update_position("go2_b", 0.5, 0.5)   # dist ~ 0.71m → CONFLICT

    print("  Simulating proximity conflict (0.71m apart)...")
    await resolver._check()

    paused = [
        rid for rid, s in scheduler._states.items()
        if s.status == RobotStatus.PAUSED
    ]
    print(f"  Paused robots: {paused}")
    print(f"  Conflict events: {len(resolver.get_conflicts())}")

    # Now move them apart → should auto-resume
    scheduler.update_position("go2_a", 0.0,  0.0)
    scheduler.update_position("go2_b", 2.5, 2.5)   # dist ~ 3.5m > 2.0m

    print("\n  Simulating separation (3.5m apart) → should resume...")
    await resolver._check()

    active = [
        rid for rid, s in scheduler._states.items()
        if s.status == RobotStatus.ACTIVE
    ]
    print(f"  Active robots: {active}")

    await scheduler.stop()
    return len(paused) > 0


async def main():
    print("\nNEXUS Phase 5 — FlexCell Test Suite")
    print(DIVIDER)

    results = {}

    try:
        results["decomposer"]        = await test_decomposer()
    except Exception as e:
        print(f"  ERROR: {e}")
        results["decomposer"]        = False

    try:
        results["scheduler"]         = await test_scheduler()
    except Exception as e:
        print(f"  ERROR: {e}")
        results["scheduler"]         = False

    try:
        results["conflict_resolver"] = await test_conflict_resolver()
    except Exception as e:
        print(f"  ERROR: {e}")
        results["conflict_resolver"] = False

    # Summary
    print(f"\n{DIVIDER}")
    print("RESULTS")
    print(DIVIDER)
    all_pass = True
    for name, passed in results.items():
        mark = "✅" if passed else "❌"
        print(f"  {mark}  {name}")
        if not passed:
            all_pass = False

    print(DIVIDER)
    if all_pass:
        print("ALL TESTS PASSED — Phase 5 backend ready.")
        print("Next: fleet_node.py + Gazebo multi-robot world")
    else:
        print("Some tests failed. Fix before proceeding.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
'''

# ════════════════════════════════════════════════════════════════════════════
# MAIN — Create all files
# ════════════════════════════════════════════════════════════════════════════

def create_files():
    created = 0
    skipped = 0
    errors  = 0

    for rel_path, content in FILES.items():
        target = ROOT / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            print(f"  [SKIP]    {rel_path}  (already exists)")
            skipped += 1
            continue

        try:
            target.write_text(content, encoding="utf-8")
            print(f"  [CREATE]  {rel_path}")
            created += 1
        except Exception as e:
            print(f"  [ERROR]   {rel_path} → {e}")
            errors += 1

    print(f"\n{'='*50}")
    print(f"  Created : {created}")
    print(f"  Skipped : {skipped}")
    print(f"  Errors  : {errors}")
    print(f"{'='*50}")


if __name__ == "__main__":
    print("\nNEXUS Phase 5 — FlexCell File Generator")
    print("=" * 50)
    print(f"Root: {ROOT}")
    print()
    create_files()

    print("\nNext steps:")
    print("  1. cd ~/projects/nexus")
    print("  2. source backend/venv/bin/activate")
    print("  3. python setup_phase5_flexcell.py")
    print("  4. cd backend")
    print("  5. python modules/flexcell/test_flexcell.py")
    print()
