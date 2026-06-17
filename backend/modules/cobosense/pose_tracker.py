"""
CoboSense — Pose Tracker (Layer 3 Safety)
ISO/TS 15066 Speed + Separation Monitoring
RAM: ~200MB (MediaPipe Lite model, complexity=0)
Frame rule: process only EVEN frames (odd → YOLO placeholder)
"""

import cv2
try:
    import mediapipe as mp
    _MP_OK = True
except ImportError:
    mp = None
    _MP_OK = False
import numpy as np
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

# ── Zone thresholds ────────────────────────────────────────
ZONE_A_MAX_M = 1.5    # < 1.5m → HARD STOP
ZONE_B_MAX_M = 3.0    # 1.5–3.0m → slow 20%
# > 3.0m → Zone C normal

# ── Monocular distance params ──────────────────────────────
SHOULDER_REAL_M = 0.45      # avg adult shoulder width
FOCAL_LENGTH_PX = 600.0     # tune per camera (see calibrate())

ZONE_COLORS = {
    "A": (0, 0, 255),
    "B": (0, 165, 255),
    "C": (0, 200, 0),
    "NONE": (180, 180, 180),
}


@dataclass
class PoseResult:
    zone: str
    distance_m: float
    human_detected: bool
    landmarks: Optional[List[dict]]
    frame_annotated: Optional[np.ndarray]
    timestamp: float = field(default_factory=time.time)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "zone": self.zone,
            "distance_m": self.distance_m,
            "human_detected": self.human_detected,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            # landmarks excluded from WS broadcast (too large)
        }


class PoseTracker:
    """
    Singleton-style pose tracker.
    Init once in FastAPI lifespan, reuse across frames.
    """

    def __init__(
        self,
        model_complexity: int = 0,
        min_detection_conf: float = 0.5,
        min_tracking_conf: float = 0.5,
    ):
        self._mp_pose = mp.solutions.pose
        self._mp_draw = mp.solutions.drawing_utils
        self._mp_styles = mp.solutions.drawing_styles

        self.pose = self._mp_pose.Pose(
            static_image_mode=False,
            model_complexity=model_complexity,   # 0=Lite ~120MB
            smooth_landmarks=True,
            min_detection_confidence=min_detection_conf,
            min_tracking_confidence=min_tracking_conf,
        )
        self._frame_idx = 0
        logger.info(
            f"PoseTracker ready — complexity={model_complexity}, "
            f"focal={FOCAL_LENGTH_PX}px"
        )

    # ── Distance estimate ──────────────────────────────────
    def _estimate_distance(self, landmarks, frame_w: int) -> float:
        try:
            L = landmarks[self._mp_pose.PoseLandmark.LEFT_SHOULDER]
            R = landmarks[self._mp_pose.PoseLandmark.RIGHT_SHOULDER]
            shoulder_px = abs(R.x - L.x) * frame_w
            if shoulder_px < 5:
                return 999.0
            return round((SHOULDER_REAL_M * FOCAL_LENGTH_PX) / shoulder_px, 2)
        except Exception:
            return 999.0

    # ── Zone classifier ────────────────────────────────────
    @staticmethod
    def classify_zone(dist: float) -> str:
        if dist <= ZONE_A_MAX_M:
            return "A"
        elif dist <= ZONE_B_MAX_M:
            return "B"
        return "C"

    # ── Main process ───────────────────────────────────────
    def process_frame(self, frame_bgr: np.ndarray) -> PoseResult:
        self._frame_idx += 1
        h, w = frame_bgr.shape[:2]

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self.pose.process(rgb)
        rgb.flags.writeable = True

        annotated = frame_bgr.copy()

        if not results.pose_landmarks:
            cv2.putText(
                annotated, "No Human", (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, ZONE_COLORS["NONE"], 2
            )
            return PoseResult(
                zone="NONE", distance_m=999.0,
                human_detected=False, landmarks=None,
                frame_annotated=annotated,
            )

        # Draw skeleton
        self._mp_draw.draw_landmarks(
            annotated,
            results.pose_landmarks,
            self._mp_pose.POSE_CONNECTIONS,
            self._mp_styles.get_default_pose_landmarks_style(),
        )

        dist = self._estimate_distance(results.pose_landmarks.landmark, w)
        zone = self.classify_zone(dist)
        color = ZONE_COLORS[zone]

        # HUD bar
        cv2.rectangle(annotated, (0, 0), (w, 55), (0, 0, 0), -1)
        cv2.putText(
            annotated,
            f"Zone {zone}  |  {dist:.2f} m",
            (12, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 2,
        )

        # Zone A red border
        if zone == "A":
            cv2.rectangle(annotated, (0, 0), (w-1, h-1), (0, 0, 255), 8)
            cv2.putText(
                annotated, "!! STOP !!",
                (w//2 - 80, h//2),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3
            )

        conf = float(
            results.pose_landmarks.landmark[
                self._mp_pose.PoseLandmark.NOSE
            ].visibility
        )

        lm_list = [
            {"x": lm.x, "y": lm.y, "z": lm.z, "v": lm.visibility}
            for lm in results.pose_landmarks.landmark
        ]

        return PoseResult(
            zone=zone,
            distance_m=dist,
            human_detected=True,
            landmarks=lm_list,
            frame_annotated=annotated,
            confidence=round(conf, 3),
        )

    async def process_frame_async(
        self, frame_bgr: np.ndarray
    ) -> PoseResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.process_frame, frame_bgr)

    def calibrate(self, known_dist_m: float, shoulder_px: float):
        """Call once with known distance to tune focal length."""
        global FOCAL_LENGTH_PX
        FOCAL_LENGTH_PX = (shoulder_px * known_dist_m) / SHOULDER_REAL_M
        logger.info(f"Focal length calibrated: {FOCAL_LENGTH_PX:.1f}px")

    def close(self):
        self.pose.close()
        logger.info("PoseTracker closed")
