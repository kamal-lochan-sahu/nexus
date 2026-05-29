"""
EmbodiedGPT — YOLO Object Detector
Model: YOLOv8n (~6MB, ~200MB RAM)
Inference: ~300ms CPU
RAM RULE: Never load simultaneously with CLIP
FRAME RULE: Alternate frames only (odd frames)
"""
from ultralytics import YOLO
import numpy as np
import logging
import time

logger = logging.getLogger(__name__)

# COCO classes YOLO already knows — plus custom factory labels
FACTORY_LABELS = {
    "person", "bottle", "cup", "chair", "table",
    "box", "suitcase", "backpack", "laptop", "cell phone"
}

class YOLODetector:
    """Singleton — load once, reuse always."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def load(self, model_path: str = None):
        if self._loaded:
            return
        if model_path is None:
            import os
            model_path = os.path.expanduser(
                "~/projects/nexus/models/yolov8n.pt"
            )
        logger.info(f"Loading YOLOv8n from {model_path}...")
        self.model = YOLO(model_path)
        self._loaded = True
        # Warmup
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        self.detect_objects(dummy)
        logger.info("YOLOv8n loaded + warmup done")

    def detect_objects(self, frame: np.ndarray,
                       conf_threshold: float = 0.35) -> list:
        """
        Input:  numpy array (H, W, 3) BGR
        Output: list of dicts:
          [{label, confidence, bbox:[x,y,w,h], distance_estimate}]
        """
        if not self._loaded:
            self.load()

        results = self.model(
            frame,
            conf=conf_threshold,
            verbose=False,
            device="cpu"
        )

        detections = []
        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                w = x2 - x1
                h = y2 - y1
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = self.model.names[cls_id]

                # Distance estimate — bbox size heuristic
                # Larger bbox = closer object
                area_ratio = (w * h) / (frame.shape[0] * frame.shape[1])
                if area_ratio > 0.3:
                    dist = "0.5-1m"
                elif area_ratio > 0.1:
                    dist = "1-2m"
                elif area_ratio > 0.03:
                    dist = "2-4m"
                else:
                    dist = "4m+"

                detections.append({
                    "label": label,
                    "confidence": round(conf, 3),
                    "bbox": [int(x1), int(y1), int(w), int(h)],
                    "distance_estimate": dist,
                    "center": [int(x1 + w/2), int(y1 + h/2)]
                })

        # Sort by confidence
        return sorted(detections, key=lambda x: x["confidence"], reverse=True)

    def draw_boxes(self, frame: np.ndarray, detections: list) -> np.ndarray:
        """Draw bounding boxes on frame — for VisionFeed component."""
        import cv2
        out = frame.copy()
        for d in detections:
            x, y, w, h = d["bbox"]
            cv2.rectangle(out, (x, y), (x+w, y+h), (0, 255, 0), 2)
            label = f"{d['label']} {d['confidence']:.2f} {d['distance_estimate']}"
            cv2.putText(out, label, (x, y-8),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        return out
