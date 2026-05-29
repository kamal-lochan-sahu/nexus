"""
EmbodiedGPT — VLA Engine
Combines: CLIP + YOLO + Groq → action plan
Pipeline: frame → encode → detect → prompt → plan → safety → execute
SEQUENTIAL RULE: CLIP first, then YOLO, then Groq. Never parallel.
"""
import os
import json
import time
import logging
import numpy as np
import cv2
from typing import Optional

from clip_encoder import CLIPEncoder
from yolo_detector import YOLODetector

logger = logging.getLogger(__name__)

# Groq setup
try:
    from groq import Groq
    _groq_token_path = os.path.expanduser("~/projects/nexus/.groq_token")
    with open(_groq_token_path) as f:
        _groq_key = f.read().strip()
    groq_client = Groq(api_key=_groq_key)
    GROQ_OK = True
    logger.info("Groq client initialized")
except Exception as e:
    GROQ_OK = False
    logger.warning(f"Groq not available: {e}")

VLA_SYSTEM_PROMPT = """You are a Vision-Language-Action (VLA) controller for a quadruped robot (Unitree Go2).
You receive visual scene information and a natural language command.
You must output a JSON action plan.

RULES:
- Output ONLY valid JSON, no markdown, no explanation
- velocity max: 0.5 m/s
- approach_distance: 0.3-1.0m from target
- If target not detected, set intent to "search" with scan action
- safety_check: "clear" always (safety module handles separately)

OUTPUT FORMAT:
{
  "original_input": "<command>",
  "module_used": "embodied_gpt",
  "intent": "<visual_navigate|search|inspect|stop>",
  "visual_context": {
    "detected_objects": [...],
    "scene_summary": "<short description>",
    "clip_confidence": <0.0-1.0>,
    "target_found": <true|false>
  },
  "plan": [
    {"step": 1, "action": "<navigate|rotate|stop|search>",
     "params": {"target": "<label>", "approach_distance": 0.5, "velocity": 0.3}}
  ],
  "safety_check": "clear",
  "confidence": <0.0-1.0>
}"""


class VLAEngine:
    """Main VLA pipeline — sequential CLIP → YOLO → Groq."""

    def __init__(self):
        self.clip = CLIPEncoder()
        self.yolo = YOLODetector()
        self.frame_count = 0
        self._initialized = False

    def initialize(self):
        """Load models at startup — warmup included."""
        if self._initialized:
            return
        logger.info("VLA Engine initializing...")
        import subprocess
        r = subprocess.run(['free', '-h'], capture_output=True, text=True)
        logger.info(f"RAM before init: {r.stdout.split(chr(10))[1]}")

        # Load CLIP (warmup inside load())
        self.clip.load()

        # Load YOLO (warmup inside load())
        self.yolo.load()

        self._initialized = True
        r = subprocess.run(['free', '-h'], capture_output=True, text=True)
        logger.info(f"RAM after init:  {r.stdout.split(chr(10))[1]}")
        logger.info("VLA Engine ready")

    def process(self, frame: np.ndarray, command: str) -> dict:
        """
        Full VLA pipeline.
        Input:  frame (H,W,3 BGR), command string
        Output: VLA JSON dict
        """
        if not self._initialized:
            self.initialize()

        t_start = time.time()
        self.frame_count += 1

        # ── Step 1: CLIP encode (every frame — scene understanding)
        logger.info("Step 1/4: CLIP encoding...")
        t0 = time.time()
        scene_vec = self.clip.encode_frame(frame)
        clip_ms = (time.time() - t0) * 1000
        logger.info(f"  CLIP done: {clip_ms:.0f}ms")

        # CLIP similarity with command
        clip_sim = self.clip.similarity(frame, command)

        # ── Step 2: YOLO detect (alternate frames)
        detections = []
        if self.frame_count % 2 == 1:  # odd frames only
            logger.info("Step 2/4: YOLO detecting...")
            t0 = time.time()
            detections = self.yolo.detect_objects(frame)
            yolo_ms = (time.time() - t0) * 1000
            logger.info(f"  YOLO done: {yolo_ms:.0f}ms, {len(detections)} objects")
        else:
            logger.info("Step 2/4: YOLO skipped (even frame)")

        # ── Step 3: Build Groq prompt
        logger.info("Step 3/4: Building Groq prompt...")
        scene_summary = self._build_scene_summary(command, detections, clip_sim)
        target_found = self._check_target_in_detections(command, detections)
        groq_prompt = self._build_prompt(command, detections, scene_summary,
                                          clip_sim, target_found)

        # ── Step 4: Groq generate action plan
        logger.info("Step 4/4: Groq generating plan...")
        t0 = time.time()
        plan_json = self._groq_generate(groq_prompt, command, detections,
                                         scene_summary, clip_sim, target_found)
        groq_ms = (time.time() - t0) * 1000
        logger.info(f"  Groq done: {groq_ms:.0f}ms")

        total_ms = (time.time() - t_start) * 1000
        logger.info(f"VLA cycle complete: {total_ms:.0f}ms total")

        return plan_json

    def _build_scene_summary(self, command: str, detections: list,
                              clip_sim: float) -> str:
        """Build human-readable scene summary."""
        if not detections:
            return f"scene visible, no objects detected confidently (CLIP sim: {clip_sim:.2f})"
        labels = [d["label"] for d in detections[:5]]
        return f"detected: {', '.join(labels)} (CLIP sim: {clip_sim:.2f})"

    def _check_target_in_detections(self, command: str,
                                     detections: list) -> bool:
        """Check if command target is in YOLO detections."""
        cmd_lower = command.lower()
        for d in detections:
            if d["label"].lower() in cmd_lower:
                return True
            # Fuzzy: "marker" matches "stop sign", "bottle" etc
            words = cmd_lower.split()
            for word in words:
                if len(word) > 3 and word in d["label"].lower():
                    return True
        return False

    def _build_prompt(self, command: str, detections: list,
                      scene_summary: str, clip_sim: float,
                      target_found: bool) -> str:
        det_str = json.dumps(detections[:5], indent=2) if detections else "[]"
        return f"""Command: "{command}"

Visual Context:
- CLIP scene similarity: {clip_sim:.3f}
- Target found by YOLO: {target_found}
- Detected objects: {det_str}
- Scene summary: {scene_summary}

Generate navigation action plan as JSON."""

    def _groq_generate(self, prompt: str, command: str, detections: list,
                        scene_summary: str, clip_sim: float,
                        target_found: bool) -> dict:
        """Call Groq or fallback to rule-based plan."""

        # Groq call
        if GROQ_OK:
            try:
                resp = groq_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": VLA_SYSTEM_PROMPT},
                        {"role": "user",   "content": prompt}
                    ],
                    max_tokens=512,
                    temperature=0.1,
                    timeout=5.0
                )
                raw = resp.choices[0].message.content.strip()
                # Strip markdown if present
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                result = json.loads(raw)
                result["original_input"] = command
                result["module_used"] = "embodied_gpt"
                return result
            except Exception as e:
                logger.warning(f"Groq failed: {e} — using fallback")

        # Fallback rule-based plan
        return self._fallback_plan(command, detections, scene_summary,
                                    clip_sim, target_found)

    def _fallback_plan(self, command: str, detections: list,
                        scene_summary: str, clip_sim: float,
                        target_found: bool) -> dict:
        """Rule-based fallback when Groq unavailable."""
        if target_found and detections:
            target = detections[0]
            plan = [{"step": 1, "action": "navigate",
                     "params": {"target": target["label"],
                                "approach_distance": 0.5, "velocity": 0.3}}]
            intent = "visual_navigate"
            confidence = target["confidence"]
        else:
            plan = [{"step": 1, "action": "search",
                     "params": {"rotate_speed": 0.2, "scan_angle": 360}}]
            intent = "search"
            confidence = clip_sim

        return {
            "original_input": command,
            "module_used": "embodied_gpt",
            "intent": intent,
            "visual_context": {
                "detected_objects": detections[:3],
                "scene_summary": scene_summary,
                "clip_confidence": round(clip_sim, 3),
                "target_found": target_found
            },
            "plan": plan,
            "safety_check": "clear",
            "confidence": round(confidence, 3)
        }
