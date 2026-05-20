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
