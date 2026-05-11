#!/usr/bin/env python3
"""
NEXUS — CoboSense main.py patch script
Run once → main.py automatically update ho jayega
"""

import re

MAIN_PATH = "/home/kamal/projects/nexus/backend/main.py"

with open(MAIN_PATH, "r") as f:
    src = f.read()

# ── PATCH 1: CoboSense import add karo (asynccontextmanager ke baad) ──
OLD_LIFESPAN_IMPORT = "from contextlib import asynccontextmanager"
NEW_LIFESPAN_IMPORT = """from contextlib import asynccontextmanager

# ── CoboSense imports ─────────────────────────────────────────────
from modules.cobosense.cobosense_service import CoboSenseService
from modules.cobosense.cobosense_router import cobosense_router, set_service"""

src = src.replace(OLD_LIFESPAN_IMPORT, NEW_LIFESPAN_IMPORT)

# ── PATCH 2: lifespan startup mein CoboSense task add karo ──
OLD_LIFESPAN = """    from backend.modules.cognitive_twin.scheduler import start_scheduler, stop_scheduler, set_broadcast_fn
    set_broadcast_fn(broadcast_twin_update)
    start_scheduler()
    yield
    stop_scheduler()"""

NEW_LIFESPAN = """    from backend.modules.cognitive_twin.scheduler import start_scheduler, stop_scheduler, set_broadcast_fn
    set_broadcast_fn(broadcast_twin_update)
    start_scheduler()

    # ── CoboSense — Layer 3 Safety (always-on) ───────────────────
    cobosense_svc = CoboSenseService(
        camera_index=0,
        broadcast_callback=broadcast_safety_update,
        fps_target=15,
    )
    set_service(cobosense_svc)
    app.state.cobosense = cobosense_svc
    asyncio.create_task(cobosense_svc.run_loop())
    print("[NEXUS] CoboSense Layer 3 Safety — ACTIVE")

    yield

    stop_scheduler()
    cobosense_svc.stop()"""

src = src.replace(OLD_LIFESPAN, NEW_LIFESPAN)

# ── PATCH 3: Router register karo (app init ke baad, CORS ke pehle) ──
OLD_CORS = "# CORS — frontend (Next.js :3000) ko allow karo"
NEW_CORS = """# ── Routers ──────────────────────────────────────────────────────
# app.include_router(cobosense_router)   # /safety/* endpoints

# CORS — frontend (Next.js :3000) ko allow karo"""

src = src.replace(OLD_CORS, NEW_CORS)

# ── PATCH 4: safety payload in build_ws_payload ──
OLD_RETURN = """    return {
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
    }"""

NEW_RETURN = """    # CoboSense safety payload
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
    }"""

src = src.replace(OLD_RETURN, NEW_RETURN)

# ── PATCH 5: broadcast_safety_update function add karo ──
OLD_BROADCAST = """async def broadcast_twin_update(data: dict):"""
NEW_BROADCAST = """async def broadcast_safety_update(data: dict):
    \"\"\"CoboSense → WebSocket broadcast (every frame with human detected).\"\"\"
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


async def broadcast_twin_update(data: dict):"""

src = src.replace(OLD_BROADCAST, NEW_BROADCAST)

# ── Write patched file ──
with open(MAIN_PATH, "w") as f:
    f.write(src)

print("✅ main.py patched successfully!")
print()
print("Changes made:")
print("  1. CoboSenseService + router imported")
print("  2. CoboSense background task — lifespan startup")
print("  3. cobosense_router registered (/safety/*)")
print("  4. 'safety' key added to WebSocket payload")
print("  5. broadcast_safety_update() function added")
print()
print("Next: python backend/main.py se server start karo")
