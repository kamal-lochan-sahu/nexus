"""
HOW TO ADD CoboSense to your existing main.py
Copy-paste these additions into the correct locations.
"""

# ── 1. IMPORTS (top of main.py) ───────────────────────────
from modules.cobosense.cobosense_service import CoboSenseService
from modules.cobosense.cobosense_router import cobosense_router, set_service
import asyncio

# ── 2. ROUTER (after app = FastAPI(...)) ──────────────────
# app.include_router(cobosense_router)

# ── 3. LIFESPAN — add inside your startup/lifespan block ──
# async def broadcast_ws(payload: dict):
#     """Pass to CoboSenseService — forwards to all WS clients."""
#     for ws in active_connections:          # your existing WS list
#         try:
#             await ws.send_json(payload)
#         except Exception:
#             pass
#
# cobosense_svc = CoboSenseService(
#     camera_index=0,
#     broadcast_callback=broadcast_ws,
#     fps_target=15,
# )
# set_service(cobosense_svc)
# asyncio.create_task(cobosense_svc.run_loop())

# ── 4. SHUTDOWN — add in shutdown event ───────────────────
# cobosense_svc.stop()

# ── That's it. CoboSense is now always-on. ────────────────
