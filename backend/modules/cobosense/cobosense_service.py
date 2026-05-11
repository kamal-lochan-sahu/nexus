"""
CoboSense — Main Service (Background asyncio Task)
Ties together: PoseTracker + IntentClassifier + SpeedController
Always-on while FastAPI server is running.
"""

import asyncio
import cv2
import time
import logging
from typing import Optional, Callable

from .pose_tracker import PoseTracker, PoseResult
from .intent_lstm import IntentClassifier
from .speed_controller import SpeedController

logger = logging.getLogger(__name__)


class CoboSenseService:
    """
    Runs as asyncio background task.
    Publishes safety payload via callback (WebSocket broadcast).
    """

    def __init__(
        self,
        camera_index: int = 0,
        broadcast_callback: Optional[Callable] = None,
        fps_target: int = 15,
    ):
        self.camera_index = camera_index
        self.broadcast = broadcast_callback    # async fn(payload)
        self.fps_target = fps_target
        self.frame_interval = 1.0 / fps_target

        self.pose_tracker = PoseTracker(model_complexity=0)
        self.intent_clf   = IntentClassifier()
        self.speed_ctrl   = SpeedController(base_speed=0.5)

        self._running = False
        self._current_payload: dict = {
            "human_detected": False,
            "zone": "NONE",
            "distance_m": 999.0,
            "intent": "static",
            "intent_conf": 1.0,
            "speed_override": 0.5,
            "speed_multiplier": 1.0,
            "incidents_today": 0,
            "last_incident_ts": None,
        }

    def start(self):
        """Load model + mark running."""
        self.intent_clf.load()   # ok if model not found — defaults to static
        self._running = True
        logger.info("CoboSenseService started")

    def stop(self):
        self._running = False
        self.pose_tracker.close()
        logger.info("CoboSenseService stopped")

    @property
    def current_payload(self) -> dict:
        return self._current_payload

    async def run_loop(self):
        """Main async loop — call as asyncio.create_task()"""
        self.start()
        cap = cv2.VideoCapture(self.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, self.fps_target)

        if not cap.isOpened():
            logger.error(
                f"Camera {self.camera_index} not available. "
                "CoboSense running in simulation mode."
            )
            await self._simulation_loop()
            return

        frame_count = 0
        last_result: Optional[PoseResult] = None

        while self._running:
            t0 = time.monotonic()
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.1)
                continue

            frame_count += 1

            # Even frames → MediaPipe | Odd → skip (YOLO placeholder)
            if frame_count % 2 == 0:
                result = await self.pose_tracker.process_frame_async(frame)
                last_result = result
            else:
                result = last_result  # reuse previous

            if result is None:
                await asyncio.sleep(self.frame_interval)
                continue

            # Intent prediction
            intent, conf = self.intent_clf.update(result.landmarks)

            # Speed calculation
            payload = self.speed_ctrl.build_safety_payload(
                zone=result.zone,
                distance_m=result.distance_m,
                intent=intent,
                intent_conf=conf,
                human_detected=result.human_detected,
                current_cmd_vel=0.5,
            )

            self._current_payload = payload

            # Broadcast to WebSocket clients
            if self.broadcast:
                try:
                    await self.broadcast({"safety": payload})
                except Exception as e:
                    logger.debug(f"Broadcast error: {e}")

            # Maintain target FPS
            elapsed = time.monotonic() - t0
            sleep_t = max(0.0, self.frame_interval - elapsed)
            await asyncio.sleep(sleep_t)

        cap.release()

    async def _simulation_loop(self):
        """Fallback if no camera — cycles through zones for testing."""
        logger.info("CoboSense simulation mode active")
        import math
        t = 0
        while self._running:
            # Simulate human cycling through zones
            dist = 1.0 + 2.5 * abs(math.sin(t * 0.1))
            zone = PoseTracker.classify_zone(dist)
            intent = "approaching" if math.sin(t * 0.1) > 0 else "leaving"
            payload = self.speed_ctrl.build_safety_payload(
                zone=zone, distance_m=round(dist, 2),
                intent=intent, intent_conf=0.85,
                human_detected=True, current_cmd_vel=0.5,
            )
            self._current_payload = payload
            if self.broadcast:
                try:
                    await self.broadcast({"safety": payload})
                except Exception:
                    pass
            t += 1
            await asyncio.sleep(0.5)
