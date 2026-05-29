"""
EmbodiedGPT — VLA Engine v2
Fixes: SIGALRM Groq timeout + CLIP text cache
"""
import os, json, time, logging, warnings, signal
import numpy as np

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

VLA_SYSTEM_PROMPT = """You are a VLA controller for Unitree Go2 robot.
Output ONLY valid JSON. No markdown. No explanation.
velocity max=0.5, approach_distance=0.3-1.0m.
FORMAT: {"original_input":"...","module_used":"embodied_gpt","intent":"visual_navigate|search","visual_context":{"detected_objects":[...],"scene_summary":"...","clip_confidence":0.0,"target_found":false},"plan":[{"step":1,"action":"navigate|search","params":{"target":"...","approach_distance":0.5,"velocity":0.3}}],"safety_check":"clear","confidence":0.0}"""


class _GroqTimeout(Exception):
    pass

def _sigalrm_handler(signum, frame):
    raise _GroqTimeout()


class VLAEngine:
    def __init__(self):
        self.clip = CLIPEncoder()
        self.yolo = YOLODetector()
        self.frame_count = 0
        self._initialized = False
        self._text_cache = {}  # command → text vector cache

    def initialize(self):
        if self._initialized:
            return
        logger.info("VLA Engine initializing...")
        self.clip.load()
        self.yolo.load()
        self._initialized = True
        logger.info("VLA Engine ready")

    def _encode_text_cached(self, command: str) -> np.ndarray:
        """Cache text encoding — same command pe CLIP text inference skip"""
        if command not in self._text_cache:
            self._text_cache[command] = self.clip.encode_text(command)
            # Keep cache small
            if len(self._text_cache) > 10:
                self._text_cache.pop(next(iter(self._text_cache)))
        return self._text_cache[command]

    def process(self, frame: np.ndarray, command: str) -> dict:
        if not self._initialized:
            self.initialize()
        t_start = time.time()
        self.frame_count += 1

        # Step 1: CLIP encode frame only (text cached)
        logger.info("Step 1/4: CLIP encoding...")
        t0 = time.time()
        img_vec = self.clip.encode_frame(frame)
        txt_vec = self._encode_text_cached(command)
        clip_sim = float(np.dot(img_vec, txt_vec))
        logger.info(f"  CLIP: {(time.time()-t0)*1000:.0f}ms sim={clip_sim:.3f}")

        # Step 2: YOLO (odd frames)
        detections = []
        if self.frame_count % 2 == 1:
            logger.info("Step 2/4: YOLO detecting...")
            t0 = time.time()
            detections = self.yolo.detect_objects(frame)
            logger.info(f"  YOLO: {(time.time()-t0)*1000:.0f}ms {len(detections)} objects")
        else:
            logger.info("Step 2/4: YOLO skipped (even frame)")

        # Step 3: Context
        target_found = any(
            w in d["label"].lower()
            for d in detections
            for w in command.lower().split() if len(w) > 3
        )
        scene_summary = (
            "detected: " + ", ".join(d["label"] for d in detections[:4])
            if detections else "no objects detected"
        ) + f" | sim={clip_sim:.2f}"

        # Step 4: Groq with SIGALRM timeout (8s, Linux-native)
        logger.info("Step 4/4: Groq generating plan...")
        t0 = time.time()
        result = self._groq_call(command, detections, scene_summary,
                                  clip_sim, target_found)
        logger.info(f"  Groq: {(time.time()-t0)*1000:.0f}ms")
        logger.info(f"VLA total: {(time.time()-t_start)*1000:.0f}ms")
        return result

    def _groq_call(self, command, detections, scene_summary,
                    clip_sim, target_found) -> dict:
        if not GROQ_OK:
            return self._fallback(command, detections, scene_summary,
                                   clip_sim, target_found)
        prompt = (f'Command: "{command}"\n'
                  f"CLIP sim: {clip_sim:.3f} | Target found: {target_found}\n"
                  f"Objects: {json.dumps(detections[:3])}\n"
                  f"Scene: {scene_summary}\nGenerate JSON plan.")
        try:
            # SIGALRM: Linux-native 8s hard timeout
            signal.signal(signal.SIGALRM, _sigalrm_handler)
            signal.alarm(8)
            resp = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": VLA_SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt}
                ],
                max_tokens=350,
                temperature=0.1
            )
            signal.alarm(0)  # Cancel alarm
            raw = resp.choices[0].message.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw.strip())
            result["original_input"] = command
            result["module_used"] = "embodied_gpt"
            return result
        except _GroqTimeout:
            signal.alarm(0)
            logger.warning("Groq SIGALRM timeout (8s) — fallback")
        except Exception as e:
            signal.alarm(0)
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
