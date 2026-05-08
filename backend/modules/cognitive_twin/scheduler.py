"""
scheduler.py — APScheduler background tasks
LSTM prediction har 5 min
WebSocket alert agar critical
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from backend.modules.cognitive_twin.lstm_predictor import get_predictor

_scheduler: AsyncIOScheduler | None = None
_ws_broadcast_fn = None  # FastAPI se inject hoga


def set_broadcast_fn(fn):
    """FastAPI apna WebSocket broadcast function inject karega"""
    global _ws_broadcast_fn
    _ws_broadcast_fn = fn


async def _run_lstm_cycle():
    """Har 5 min mein yeh run hoga"""
    predictor = get_predictor()
    alerts = await predictor.run_and_store()

    # Critical alert hai toh WebSocket broadcast karo
    if alerts > 0 and _ws_broadcast_fn:
        from backend.database.crud import get_active_forecasts
        forecasts = await get_active_forecasts()
        criticals = [f for f in forecasts if f["severity"] == "critical"]
        if criticals:
            f = criticals[0]
            await _ws_broadcast_fn({
                "type": "twin_alert",
                "joint": f["joint_name"],
                "fail_in_hours": f["fail_in_hours"],
                "confidence": f["confidence"],
                "severity": f["severity"],
            })
            print(f"[Scheduler] 🚨 Alert broadcast: {f['joint_name']} critical")


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _run_lstm_cycle,
        trigger=IntervalTrigger(minutes=5),
        id="lstm_prediction",
        replace_existing=True,
        max_instances=1,        # overlap nahi hoga
    )
    _scheduler.start()
    print("[Scheduler] ✅ Started — LSTM runs every 5 min")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[Scheduler] Stopped")
