"""
CoboSense — LSTM Intent Classifier
Classes: 0=static, 1=leaving, 2=approaching
Input : (batch, 10, 66)  — 10 timesteps × 33 landmarks × 2 coords
RAM   : ~150MB inference
"""

try:
    import torch
    import torch.nn as nn
    _TORCH_OK = True
except ImportError:
    torch = None
    nn = None
    _TORCH_OK = False
import numpy as np
import os
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

INTENT_LABELS = {0: "static", 1: "leaving", 2: "approaching"}
MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../../models/lstm_cobosense/model.pt"
)
SEQ_LEN = 10
N_FEATURES = 66   # 33 landmarks × (x, y)


class CoboLSTM(nn.Module):
    def __init__(self, input_size=66, hidden1=64, hidden2=32, n_classes=3):
        super().__init__()
        self.lstm1 = nn.LSTM(input_size, hidden1, batch_first=True)
        self.drop1 = nn.Dropout(0.2)
        self.lstm2 = nn.LSTM(hidden1, hidden2, batch_first=True)
        self.drop2 = nn.Dropout(0.2)
        self.fc    = nn.Linear(hidden2, n_classes)

    def forward(self, x):
        # x: (batch, seq, features)
        out, _ = self.lstm1(x)
        out = self.drop1(out)
        out, _ = self.lstm2(out)
        out = self.drop2(out)
        out = self.fc(out[:, -1, :])   # last timestep
        return out                      # logits


class IntentClassifier:
    """
    Wraps CoboLSTM for inference.
    Maintains a rolling buffer of SEQ_LEN pose frames.
    """

    def __init__(self):
        self.device = torch.device("cpu")   # always CPU on HP 241
        self.model: CoboLSTM | None = None
        self._buffer: list = []             # rolling window
        self._loaded = False

    def load(self, model_path: str = MODEL_PATH) -> bool:
        """Load model.pt — call after training on Colab."""
        if not os.path.exists(model_path):
            logger.warning(
                f"Model not found at {model_path}. "
                "Train on Colab first (Step 2). "
                "Returning STATIC as default."
            )
            return False
        try:
            self.model = CoboLSTM()
            state = torch.load(model_path, map_location=self.device)
            self.model.load_state_dict(state)
            self.model.eval()
            self._loaded = True
            logger.info(f"IntentClassifier loaded: {model_path}")
            return True
        except Exception as e:
            logger.error(f"Model load failed: {e}")
            return False

    def _landmarks_to_features(self, landmarks: list) -> np.ndarray:
        """Extract 66 features (x,y) from 33 landmarks."""
        features = []
        for lm in landmarks:
            features.extend([lm["x"], lm["y"]])
        arr = np.array(features, dtype=np.float32)
        if arr.shape[0] != N_FEATURES:
            arr = np.zeros(N_FEATURES, dtype=np.float32)
        return arr

    def update(self, landmarks: list) -> Tuple[str, float]:
        """
        Feed one frame's landmarks.
        Returns (intent_label, confidence) when buffer is full.
        Returns ("static", 1.0) as safe default otherwise.
        """
        if landmarks is None:
            self._buffer.clear()
            return "static", 1.0

        features = self._landmarks_to_features(landmarks)
        self._buffer.append(features)

        # Keep only last SEQ_LEN frames
        if len(self._buffer) > SEQ_LEN:
            self._buffer.pop(0)

        # Need full window for inference
        if len(self._buffer) < SEQ_LEN:
            return "static", 1.0   # safe default while buffering

        if not self._loaded:
            return "static", 1.0   # model not trained yet

        # Inference
        seq = np.stack(self._buffer, axis=0)                   # (10, 66)
        tensor = torch.tensor(seq).unsqueeze(0).to(self.device)# (1, 10, 66)

        with torch.no_grad():
            logits = self.model(tensor)
            probs  = torch.softmax(logits, dim=1)[0]
            idx    = int(torch.argmax(probs).item())
            conf   = float(probs[idx].item())

        return INTENT_LABELS[idx], round(conf, 3)

    def reset_buffer(self):
        self._buffer.clear()
