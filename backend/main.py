import asyncio
import json
import time
from contextlib import asynccontextmanager
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
    yield
    # Ye code server band hone pe chalta hai
    print("[NEXUS] Backend shutting down...")

# ── App init ──────────────────────────────────────────────────────
app = FastAPI(
    title="NEXUS Backend",
    description="Industry 5.0 Unified Robotics Intelligence Platform",
    version="4.0.0",
    lifespan=lifespan,
)

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
            # Placeholder: 2Hz pe dummy state bhejo
            await websocket.send_text(json.dumps({
                "type": "state_update",
                "timestamp": datetime.utcnow().isoformat(),
                "system": "online",
            }))
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
    user_text = payload.get("text", "")

    # Layer 1: Pre-LLM safety check
    pre = check_safety(user_text)
    if not pre["safe"]:
        return {"status": "rejected", "stage": "safety_pre", "reason": pre["reason"]}

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
