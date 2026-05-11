"""
FastAPI router for CoboSense endpoints.
Mount in main.py:  app.include_router(cobosense_router)
"""

from fastapi import APIRouter
from .cobosense_service import CoboSenseService

cobosense_router = APIRouter(prefix="/safety", tags=["CoboSense"])

# Global service instance (set by main.py lifespan)
_service: CoboSenseService | None = None

def set_service(svc: CoboSenseService):
    global _service
    _service = svc


@cobosense_router.get("/status")
async def safety_status():
    if _service is None:
        return {"error": "CoboSense not initialized"}
    return _service.current_payload


@cobosense_router.get("/health")
async def safety_health():
    return {
        "cobosense": "running" if _service and _service._running else "stopped",
        "iso_ts_15066": True,
    }
