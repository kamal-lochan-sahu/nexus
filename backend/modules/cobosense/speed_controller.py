"""
CoboSense — Speed Controller
Layer 3 HIGHEST PRIORITY — overrides all other modules.
Response time: < 100ms guaranteed (no blocking calls).
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Speed multipliers per zone × intent
SPEED_RULES = {
    # (zone, intent): multiplier
    ("A", "static"):     0.0,   # hard stop
    ("A", "leaving"):    0.0,   # hard stop — caution
    ("A", "approaching"):0.0,   # hard stop
    ("B", "static"):     0.2,   # 20% speed
    ("B", "leaving"):    0.3,   # 30% — leaving, slightly relax
    ("B", "approaching"):0.0,   # pre-pause — predictive SSM
    ("C", "static"):     1.0,
    ("C", "leaving"):    1.0,
    ("C", "approaching"):0.8,   # slight caution pre-entry
    ("NONE", "static"):  1.0,   # no human detected
    ("NONE", "leaving"): 1.0,
    ("NONE", "approaching"): 1.0,
}


class SpeedController:
    """
    Stateless speed multiplier calculator.
    Integrates with ROS2 /cmd_vel via bridge.py override.
    """

    def __init__(self, base_speed: float = 0.5):
        self.base_speed = base_speed          # m/s default
        self._last_override: float = 1.0
        self._last_event_time: float = 0.0
        self._incident_count: int = 0

    def get_multiplier(self, zone: str, intent: str) -> float:
        key = (zone, intent)
        mult = SPEED_RULES.get(key, 1.0)

        # Log safety events (zone A or approaching B)
        if mult == 0.0 and self._last_override != 0.0:
            self._incident_count += 1
            self._last_event_time = time.time()
            logger.warning(
                f"SAFETY EVENT #{self._incident_count} — "
                f"Zone {zone} | Intent {intent} → STOP"
            )

        self._last_override = mult
        return mult

    def get_target_speed(
        self,
        zone: str,
        intent: str,
        current_cmd_vel: Optional[float] = None,
    ) -> float:
        """
        Returns target linear.x velocity.
        If current_cmd_vel provided, applies multiplier to it.
        """
        mult = self.get_multiplier(zone, intent)
        base = current_cmd_vel if current_cmd_vel is not None else self.base_speed
        return round(abs(base) * mult, 3)

    def build_safety_payload(
        self,
        zone: str,
        distance_m: float,
        intent: str,
        intent_conf: float,
        human_detected: bool,
        current_cmd_vel: float = 0.5,
    ) -> dict:
        """Build the WebSocket safety broadcast payload."""
        mult = self.get_multiplier(zone, intent)
        override_speed = round(current_cmd_vel * mult, 3)

        return {
            "human_detected": human_detected,
            "zone": zone,
            "distance_m": distance_m,
            "intent": intent,
            "intent_conf": intent_conf,
            "speed_override": override_speed,
            "speed_multiplier": mult,
            "incidents_today": self._incident_count,
            "last_incident_ts": self._last_event_time or None,
        }

    @property
    def incident_count(self) -> int:
        return self._incident_count
