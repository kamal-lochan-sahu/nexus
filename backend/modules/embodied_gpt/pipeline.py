"""
Step 6: Full EmbodiedGPT Pipeline
Camera → CLIP → YOLO → Groq → Safety → Navigate
Entry point for FastAPI endpoint and ROS2 node
"""
import time
import logging
import numpy as np

from vla_engine import VLAEngine
from safety_validator import validate
from navigation_executor import execute_plan

logger = logging.getLogger(__name__)

class EmbodiedGPTPipeline:
    """Single entry point for entire VLA pipeline."""

    def __init__(self):
        self.engine = VLAEngine()
        self._last_frame = None
        self._last_result = None
        self.run_count = 0

    def initialize(self):
        """Call once at startup — loads CLIP + YOLO with warmup."""
        self.engine.initialize()
        logger.info("EmbodiedGPT Pipeline ready")

    def run(self, frame: np.ndarray, command: str,
            execute: bool = False) -> dict:
        """
        Full pipeline run.
        Args:
            frame:   numpy BGR frame from camera
            command: natural language command
            execute: if True, send cmd_vel to robot
        Returns:
            result dict with vla_output + execution_status
        """
        t0 = time.time()
        self.run_count += 1
        self._last_frame = frame

        # 1. VLA engine
        vla_output = self.engine.process(frame, command)

        # 2. Safety validation
        try:
            vla_output = validate(vla_output)
        except ValueError as e:
            logger.warning(f"Safety blocked: {e}")
            return {
                "vla_output": vla_output,
                "execution": {"status": "blocked", "reason": str(e)},
                "total_ms": int((time.time()-t0)*1000)
            }

        # 3. Execute (optional)
        execution = {"status": "planned"}
        if execute:
            execution = execute_plan(vla_output)

        self._last_result = vla_output
        total_ms = int((time.time()-t0)*1000)
        logger.info(f"Pipeline run #{self.run_count} complete: {total_ms}ms")

        return {
            "vla_output": vla_output,
            "execution": execution,
            "total_ms": total_ms
        }

    def get_last_result(self) -> dict:
        return self._last_result or {}
