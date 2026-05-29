"""
EmbodiedGPT — VLA Engine
Pipeline: frame → CLIP → YOLO → Groq → JSON
SEQUENTIAL: Never parallel. CLIP first, YOLO second, Groq third.
"""
import os, json, time, logging, warnings
import numpy as np
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

warnings.filterwarnings("ignore")
from clip_encoder import CLIPEncoder
from yolo_detector import YOLODetector

logger = logging.getLogger(__name__)

try:
    from groq import Groq
    with open(os.path.expanduser("~/projects/nexus/.groq_token")) as f:
        groq_client = Groq(api_key=f.read().strip())
    GROQ_OK = True
    logger.info("Groq client initialized")
except Exception as e:
    GROQ_OK = False
    logger.warning(f"Groq not available: {e}")

VLA_SYSTEM_PROMPT = """You are a VLA controller for a quadruped robot (Unitree Go2).
Output ONLY valid JSON, no markdown, no explanation.
Rules: velocity max 0.5, approach_distance 0.3-1.0m.
If target not detected, use intent=search with rotate action.

FORMAT:
{"original_input":"...","module_used":"embodied_gpt","intent":"visual_navigate|search|inspect|stop","visual_context":{"detected_objects":[...],"scene_summary":"...","clip_confidence":0.0,"target_found":false},"plan":[{"step":1,"action":"navigate|rotate|stop|search","params":{"target":"...","approach_distance":0.5,"velocity":0.3}}],"safety_check":"clear","confidence":0.0}"""


class VLAEngine:
    def __init__(self):
        self.clip = CLIPEncoder()
        self.yolo = YOLODetector()
        self.frame_count = 0
        self._initialized = False

    def initialize(self):
        if self._initialized:
            return
        logger.info("VLA Engine initializing...")
        self.clip.load()
        self.yolo.load()
        self._initialized = True
        logger.info("VLA Engine ready")

    def process(self, frame: np.ndarray, command: str) -> dict:
        if not self._initialized:
            self.initialize()
        t_start = time.time()
        self.frame_count += 1

        # Step 1: CLIP encode
        logger.info("Step 1/4: CLIP encoding...")
        t0 = time.time()
        scene_vec = self.clip.encode_frame(frame)
        clip_sim = float(np.dot(scene_vec, self.clip.encode_text(command)))
        logger.info(f"  CLIP: {(time.time()-t0)*1000:.0f}ms, sim={clip_sim:.3f}")

        # Step 2: YOLO detect (odd frames only)
        detections = []
        if self.frame_count % 2 == 1:
            logger.info("Step 2/4: YOLO detecting...")
            t0 = time.time()
            detections = self.yolo.detect_objects(frame)
            logger.info(f"  YOLO: {(time.time()-t0)*1000:.0f}ms, {len(detections)} objects")
        else:
            logger.info("Step 2/4: YOLO skipped (even frame)")

        # Step 3: Build context
        target_found = any(
            w in d["label"].lower()
            for d in detections
            for w in command.lower().split()
            if len(w) > 3
        )
        scene_summary = (
            f"detected: {', '.join(d['label'] for d in detections[:4])}"
            if detections else "no objects detected"
        ) + f" | CLIP sim={clip_sim:.2f}"

        # Step 4: Groq with 8s timeout
        logger.info("Step 4/4: Groq generating plan...")
        t0 = time.time()
        result = self._groq_with_timeout(
            command, detections, scene_summary, clip_sim, target_found
        )
        logger.info(f"  Groq: {(time.time()-t0)*1000:.0f}ms")
        logger.info(f"VLA total: {(time.time()-t_start)*1000:.0f}ms")
        return result

    def _groq_with_timeout(self, command, detections, scene_summary,
                            clip_sim, target_found) -> dict:
        if not GROQ_OK:
            return self._fallback(command, detections, scene_summary,
                                   clip_sim, target_found)
        prompt = (
            f'Command: "{command}"\n'
            f"CLIP similarity: {clip_sim:.3f}\n"
            f"Target found: {target_found}\n"
            f"Objects: {json.dumps(detections[:4])}\n"
            f"Scene: {scene_summary}\n"
            f"Generate JSON action plan."
        )
        def _call():
            return groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": VLA_SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt}
                ],
                max_tokens=400,
                temperature=0.1
            )
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                resp = ex.submit(_call).result(timeout=8.0)
            raw = resp.choices[0].message.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw.strip())
            result["original_input"] = command
            result["module_used"] = "embodied_gpt"
            return result
        except FuturesTimeout:
            logger.warning("Groq timeout (8s) — fallback")
        except Exception as e:
            logger.warning(f"Groq error: {e} — fallback")
        return self._fallback(command, detections, scene_summary,
                               clip_sim, target_found)

    def _fallback(self, command, detections, scene_summary,
                   clip_sim, target_found) -> dict:
        if target_found and detections:
            tgt = detections[0]
            plan = [{"step": 1, "action": "navigate",
                     "params": {"target": tgt["label"],
                                "approach_distance": 0.5, "velocity": 0.3}}]
            intent, conf = "visual_navigate", tgt["confidence"]
        else:
            plan = [{"step": 1, "action": "search",
                     "params": {"rotate_speed": 0.2, "scan_angle": 360}}]
            intent, conf = "search", round(clip_sim, 3)
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
            "confidence": conf
        }
