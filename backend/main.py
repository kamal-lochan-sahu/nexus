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
