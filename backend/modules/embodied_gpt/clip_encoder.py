"""
EmbodiedGPT — CLIP Encoder
Model: ViT-B/32 (~300MB RAM)
Inference: ~500ms CPU
Output: 512-dim normalized vector
RULE: Load once, keep in memory. Never run with YOLO simultaneously.
"""
import clip
import torch
import numpy as np
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class CLIPEncoder:
    """Singleton — load once, reuse always."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def load(self):
        if self._loaded:
            return
        logger.info("Loading CLIP ViT-B/32 (~300MB RAM)...")
        self.device = "cpu"
        self.model, self.preprocess = clip.load("ViT-B/32", device=self.device)
        self.model.eval()
        self._loaded = True
        logger.info("CLIP loaded OK")
        # JIT warmup — pehli inference slow hoti hai (12s), startup pe karo
        logger.info("Running warmup inference...")
        import numpy as _np_w
        dummy = _np_w.zeros((224, 224, 3), dtype=_np_w.uint8)
        self.encode_frame(dummy)
        logger.info("Warmup done — subsequent inferences ~900ms")

    def encode_frame(self, numpy_frame: np.ndarray) -> np.ndarray:
        """
        Input:  numpy array (H, W, 3) — BGR or RGB
        Output: 512-dim float32 normalized vector
        """
        if not self._loaded:
            self.load()
        # BGR → RGB → PIL (OpenCV default is BGR)
        rgb = numpy_frame[:, :, ::-1].copy()
        pil_img = Image.fromarray(rgb.astype(np.uint8))
        with torch.no_grad():
            img_input = self.preprocess(pil_img).unsqueeze(0).to(self.device)
            features = self.model.encode_image(img_input)
            features = features / features.norm(dim=-1, keepdim=True)
        return features.cpu().numpy().flatten()  # shape: (512,)

    def encode_text(self, text: str) -> np.ndarray:
        """
        Input:  text string
        Output: 512-dim float32 normalized vector
        """
        if not self._loaded:
            self.load()
        with torch.no_grad():
            tokens = clip.tokenize([text]).to(self.device)
            features = self.model.encode_text(tokens)
            features = features / features.norm(dim=-1, keepdim=True)
        return features.cpu().numpy().flatten()  # shape: (512,)

    def similarity(self, frame: np.ndarray, text: str) -> float:
        """
        Cosine similarity between frame and text query.
        Returns float 0.0 to 1.0 (higher = better match)
        """
        img_vec = self.encode_frame(frame)
        txt_vec = self.encode_text(text)
        return float(np.dot(img_vec, txt_vec))

    def top_labels(self, frame: np.ndarray, labels: list) -> list:
        """
        Rank a list of text labels by similarity to frame.
        Returns sorted list of (label, score) tuples.
        """
        if not self._loaded:
            self.load()
        img_vec = self.encode_frame(frame)
        results = []
        for label in labels:
            txt_vec = self.encode_text(label)
            score = float(np.dot(img_vec, txt_vec))
            results.append((label, round(score, 4)))
        return sorted(results, key=lambda x: x[1], reverse=True)
