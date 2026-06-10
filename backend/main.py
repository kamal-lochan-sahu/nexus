import sys
from pathlib import Path
# Project root ko path mein daalo — saare imports fix ho jayenge
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import json
import time
from contextlib import asynccontextmanager

# ── CoboSense imports ─────────────────────────────────────────────
try:
    from modules.cobosense.cobosense_service import CoboSenseService
    _cobosense_available = True
except Exception as _e:
    print(f"[NEXUS] CoboSense unavailable (mediapipe): {_e}")
    CoboSenseService = None
    _cobosense_available = False
from modules.cobosense.cobosense_router import cobosense_router, set_service

from modules.flexcell.flexcell_router import router as flexcell_router
from modules.flexcell.fleet_scheduler import get_scheduler
from modules.flexcell.conflict_resolver import get_resolver
from datetime import datetime

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# ── Startup / Shutdown ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ye code server start hone pe chalta hai
    print("[NEXUS] Backend starting...")
    app.state.start_time = time.time()
    app.state.connected_clients = []
    from backend.modules.cognitive_twin.scheduler import start_scheduler, stop_scheduler, set_broadcast_fn
    set_broadcast_fn(broadcast_twin_update)
    start_scheduler()

    # ── CoboSense — Layer 3 Safety (graceful fallback) ──────────
    cobosense_svc = None
    if _cobosense_available:
        try:
            cobosense_svc = CoboSenseService(
                camera_index=0,
                broadcast_callback=broadcast_safety_update,
                fps_target=15,
            )
            set_service(cobosense_svc)
            app.state.cobosense = cobosense_svc
            asyncio.create_task(cobosense_svc.run_loop())
            print("[NEXUS] CoboSense Layer 3 Safety — ACTIVE")
        except Exception as e:
            print(f"[NEXUS] CoboSense startup failed: {e} — running in mock mode")
            app.state.cobosense = None
    else:
        app.state.cobosense = None
        print("[NEXUS] CoboSense — mock mode (mediapipe unavailable)")

    # ── FlexCell — Multi-robot coordination ─────────────────────
    scheduler = get_scheduler()
    resolver  = get_resolver()
    await scheduler.start()
    await resolver.start()
    print("[NEXUS] FlexCell Multi-robot Coordination — ACTIVE")

    yield

    stop_scheduler()
    if cobosense_svc: cobosense_svc.stop()

    await scheduler.stop()
    await resolver.stop()
    # Ye code server band hone pe chalta hai
    print("[NEXUS] Backend shutting down...")

# ── App init ──────────────────────────────────────────────────────
app = FastAPI(
    title="NEXUS Backend",
    description="Industry 5.0 Unified Robotics Intelligence Platform",
    version="4.0.0",
    lifespan=lifespan,
)

# ── Routers ──────────────────────────────────────────────────────
app.include_router(cobosense_router)   # /safety/* endpoints

app.include_router(flexcell_router)    # /flexcell/* endpoints

# CORS — frontend (Next.js :3000) ko allow karo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── GET /health ───────────────────────────────────────────────────
@app.get("/health")
async def health():
    """System alive check — load balancer + frontend use karta hai"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "4.0.0",
    }

# ── GET /status ───────────────────────────────────────────────────
@app.get("/status")
async def status():
    """Full system status — modules + robots + uptime"""
    uptime = int(time.time() - app.state.start_time)
    return {
        "system": "online",
        "uptime_seconds": uptime,
        "modules": {
            "nl2rc":          "ready",
            "cognitive_twin": "ready",
            "cobosense":      "ready",
            "robo_rl":        "ready",
            "flexcell":       "ready",
            "embodied_gpt":   "ready",
        },
        "robots": {
            "go2_a": {"status": "standby", "battery": 100},
            "go2_b": {"status": "standby", "battery": 100},
        },
        "ws_clients": len(app.state.connected_clients),
    }

# ── WS /ws ────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket — frontend real-time updates ke liye"""
    await websocket.accept()
    app.state.connected_clients.append(websocket)
    print(f"[WS] Client connected. Total: {len(app.state.connected_clients)}")
    try:
        while True:
            payload = await build_ws_payload()
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        app.state.connected_clients.remove(websocket)
        print(f"[WS] Client disconnected. Total: {len(app.state.connected_clients)}")

# ── Entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

# ── NL2RC Imports ─────────────────────────────────────────────────
import sys
sys.path.insert(0, "/home/kamal/projects/nexus/backend")

from modules.nl2rc.safety_pre import check_safety
from modules.nl2rc.llm_engine import call_llm
from core.safety_post import validate_command
from ros2.bridge import ros_bridge

# ── POST /command ─────────────────────────────────────────────────
@app.post("/command")
async def process_command(payload: dict):
    user_text = payload.get("command", "") or payload.get("text", "")

    # Layer 1: Pre-LLM safety check
    pre = check_safety(user_text)
    if not pre["safe"]:
        return {"status": "rejected", "stage": "safety_pre", "reason": pre["reason"]}
    # u2500u2500 Phase 8: Orchestrator routing u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500u2500
    try:
        from core.orchestrator import Orchestrator
        _orch = Orchestrator()
        _res = _orch.handle(user_text)
        if _res.get("module", "nl2rc") != "nl2rc":
            return {"status": "ok", "stage": "orchestrated", "module": _res.get("module"), "result": _res}
    except Exception:
        pass

    # LLM call
    llm_result = await call_llm(user_text)
    if "error" in llm_result:
        return {"status": "error", "stage": "llm", "reason": llm_result["error"]}

    # LLM output se flat command banao
    try:
        plan_step = llm_result["plan"][0]
        params    = plan_step.get("params", {})

        # action map karo
        direction = params.get("direction", "forward")
        action_map = {
            "forward":  "move_forward",
            "backward": "move_backward",
            "left":     "turn_left",
            "right":    "turn_right",
        }
        action = action_map.get(direction, "move_forward")

        cmd_dict = {
            "action":   action,
            "distance": float(params.get("distance", 0.0)),
            "velocity": float(params.get("velocity", 0.3)),
            "confidence": float(llm_result.get("confidence", 1.0)),
        }
    except (KeyError, IndexError) as e:
        return {"status": "error", "stage": "parser", "reason": f"LLM output parse failed: {e}"}

    # Layer 2: Post-LLM safety check
    post = validate_command(cmd_dict)
    if not post["safe"]:
        return {"status": "rejected", "stage": "safety_post", "reason": post["reason"]}

    # Bridge → Robot
    final = post["command"]
    linear_x  = final.get("velocity", 0.3)
    angular_z = 0.0
    if final["action"] == "turn_left":
        linear_x, angular_z = 0.0, 0.5
    elif final["action"] == "turn_right":
        linear_x, angular_z = 0.0, -0.5
    elif final["action"] == "move_backward":
        linear_x = -linear_x

    ros_bridge.send_cmd_vel(linear_x=linear_x, angular_z=angular_z)

    return {
        "status":   "executed",
        "command":  final,
        "modified": post["modified"],
        "reason":   post["reason"],
    }


async def build_ws_payload() -> dict:
    """
    Har 500ms yeh payload build hota hai aur sabhi clients ko jaata hai.
    DB se latest state + joints + forecast fetch karta hai.
    """
    from backend.database.crud import (
        get_latest_robot_state,
        get_all_joints_latest,
        get_active_forecasts,
    )

    # Robot state
    state = await get_latest_robot_state() or {}

    # Joint health — {joint_name: {health, temp, status}}
    joints_raw = await get_all_joints_latest()
    joints = {}
    for j in joints_raw:
        name   = j["joint_name"]
        health = j["health_pct"]
        status = "ok" if health > 70 else ("warning" if health > 40 else "critical")
        joints[name] = {
            "health": round(health, 1),
            "temp":   round(j["temperature"], 1),
            "status": status,
        }

    # Latest critical/warning forecast
    forecasts = await get_active_forecasts()
    prediction = {}
    if forecasts:
        f = forecasts[0]  # highest confidence first
        prediction = {
            "joint":         f["joint_name"],
            "fail_in_hours": f["fail_in_hours"],
            "confidence":    f["confidence"],
            "severity":      f["severity"],
        }

    # CoboSense safety payload
    safety = {}
    try:
        safety = app.state.cobosense.current_payload
    except AttributeError:
        safety = {
            "human_detected": False, "zone": "NONE",
            "distance_m": 999.0, "intent": "static",
            "intent_conf": 1.0, "speed_override": 0.5,
            "speed_multiplier": 1.0, "incidents_today": 0,
        }

    return {
        "type":      "state_update",
        "timestamp": datetime.utcnow().isoformat(),
        "system":    "online",
        "robot": {
            "pos_x":       state.get("pos_x", 0.0),
            "pos_y":       state.get("pos_y", 0.0),
            "heading_deg": state.get("heading_deg", 0.0),
            "velocity":    state.get("velocity", 0.0),
            "gait":        state.get("gait", "stand"),
            "mode":        state.get("mode", "idle"),
        },
        "twin": {
            "joints":     joints,
            "prediction": prediction,
        },
        "safety": safety,

        "fleet": get_scheduler().get_fleet_status(),
    }


async def broadcast_safety_update(data: dict):
    """CoboSense → WebSocket broadcast (every frame with human detected)."""
    msg = json.dumps(data)
    dead = []
    for ws in app.state.connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        try:
            app.state.connected_clients.remove(ws)
        except ValueError:
            pass


async def broadcast_twin_update(data: dict):
    """
    APScheduler se call hota hai jab critical alert aata hai.
    Sabhi connected clients ko alert bhejta hai.
    """
    msg = json.dumps(data)
    dead = []
    for ws in app.state.connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        app.state.connected_clients.remove(ws)
    print(f"[WS] Twin alert sent to {len(app.state.connected_clients)} clients")
