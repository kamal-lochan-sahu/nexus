"""
lstm_predictor.py — LSTM-based failure prediction
Loads trained model, runs every 5 min via APScheduler
Input : last 24hr joint data from SQLite
Output: failure probability per joint → twin_forecast table
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
import pickle
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from backend.database.crud import get_joint_health_window, upsert_twin_forecast

# ── Paths ──────────────────────────────────────
MODEL_DIR  = Path(__file__).parent.parent.parent.parent / "models/lstm_twin"
MODEL_PATH  = MODEL_DIR / "model.pt"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
META_PATH   = MODEL_DIR / "meta.json"

# ── Constants ──────────────────────────────────
SEQ_LEN    = 24
N_FEATURES = 42
N_JOINTS   = 12
WARN_THRESH     = 0.7
CRITICAL_THRESH = 0.9

JOINT_NAMES = [
    "FR_hip","FR_thigh","FR_calf",
    "FL_hip","FL_thigh","FL_calf",
    "RR_hip","RR_thigh","RR_calf",
    "RL_hip","RL_thigh","RL_calf",
]


# ── Model definition (training se same hona chahiye) ──
class CognitiveTwinLSTM(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm1   = nn.LSTM(N_FEATURES, 64, batch_first=True)
        self.drop1   = nn.Dropout(0.2)
        self.lstm2   = nn.LSTM(64, 32, batch_first=True)
        self.drop2   = nn.Dropout(0.2)
        self.output  = nn.Linear(32, N_JOINTS)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        out, _ = self.lstm1(x)
        out     = self.drop1(out)
        out, _ = self.lstm2(out)
        out     = self.drop2(out)
        out     = out[:, -1, :]
        return self.sigmoid(self.output(out))


# ── Predictor class ────────────────────────────
class LSTMPredictor:
    def __init__(self):
        self.model  = None
        self.scaler = None
        self.meta   = None
        self._load()

    def _load(self):
        """Model + scaler + meta load karo"""
        if not MODEL_PATH.exists():
            print(f"[LSTM] ❌ model.pt not found at {MODEL_PATH}")
            return

        # Meta
        self.meta = json.loads(META_PATH.read_text())

        # Scaler
        with open(SCALER_PATH, "rb") as f:
            self.scaler = pickle.load(f)

        # Model
        self.model = CognitiveTwinLSTM()
        self.model.load_state_dict(
            torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
        )
        self.model.eval()
        print(f"[LSTM] ✅ Model loaded — {MODEL_PATH.name}")
        print(f"[LSTM]    Input shape : (batch, {SEQ_LEN}, {N_FEATURES})")
        print(f"[LSTM]    Outputs     : {N_JOINTS} joints")

    def _build_feature_row(self, row: dict) -> list:
        """
        SQLite row → 42-feature vector
        Order must match training: pos(12) + vel(12) + eff(12) + temp(4) + battery(1) + vib(1)
        Note: SQLite mein sirf health/temp/vibration/current hai
        Missing features zero-pad karte hain — Phase 3 mein refine hoga
        """
        health  = row.get("health_pct", 100.0) / 100.0
        temp    = row.get("temperature", 45.0)
        vibr    = row.get("vibration", 0.0)
        current = row.get("current_a", 0.0)

        # Approximate reconstruction
        pos = health * 0.4          # health se position estimate
        vel = current * 0.1         # current se velocity estimate
        eff = current * 10.0        # current → effort

        return [pos, vel, eff, temp, vibr, current]

    async def predict_all_joints(self, robot_id: str = "go2_001") -> list[dict]:
        """
        12 joints ke liye failure probability predict karo.
        Returns list of dicts for upsert_twin_forecast.
        """
        if self.model is None:
            print("[LSTM] Model not loaded — skipping prediction")
            return []

        results = []

        for joint_name in JOINT_NAMES:
            # Last 24hr data fetch karo
            rows = await get_joint_health_window(joint_name, hours=24.0, robot_id=robot_id)

            if len(rows) < SEQ_LEN:
                # Data kam hai — skip
                print(f"[LSTM] {joint_name}: only {len(rows)} rows, need {SEQ_LEN}")
                continue

            # Feature matrix build karo — last SEQ_LEN rows
            recent = rows[-SEQ_LEN:]
            features = []
            for row in recent:
                h   = row["health_pct"] / 100.0
                t   = row["temperature"]
                v   = row["vibration"]
                c   = row["current_a"]
                w   = row["wear_rate"]
                # 42 features: pad with derived values
                # pos(12): use health as proxy for all joints
                pos_vec  = [h * 0.4]        * 12
                vel_vec  = [c * 0.1]        * 12
                eff_vec  = [c * 10.0]       * 12
                temp_vec = [t]              * 4
                batt_vec = [13.5 - w * 100]     # battery estimate
                vib_vec  = [v]
                features.append(pos_vec + vel_vec + eff_vec + temp_vec + batt_vec + vib_vec)

            X = np.array(features, dtype=np.float32)  # (24, 42)

            # Normalize
            X_scaled = self.scaler.transform(X)        # (24, 42)
            X_tensor = torch.tensor(X_scaled).unsqueeze(0)  # (1, 24, 42)

            # Inference
            with torch.no_grad():
                probs = self.model(X_tensor)           # (1, 12)

            # Joint index
            j_idx = JOINT_NAMES.index(joint_name)
            prob  = float(probs[0, j_idx])

            # Severity determine karo
            if prob >= CRITICAL_THRESH:
                severity = "critical"
                action   = "immediate_maintenance"
                fail_hrs = max(1.0, (1.0 - prob) * 10)
            elif prob >= WARN_THRESH:
                severity = "warning"
                action   = "schedule_maintenance"
                fail_hrs = max(5.0, (1.0 - prob) * 48)
            else:
                severity = "ok"
                action   = "monitor"
                fail_hrs = 999.0

            results.append({
                "joint_name"   : joint_name,
                "fail_in_hours": round(fail_hrs, 1),
                "confidence"   : round(prob, 4),
                "severity"     : severity,
                "action"       : action,
            })

            if severity != "ok":
                print(f"[LSTM] ⚠️  {joint_name}: {prob:.3f} ({severity}) — fail in {fail_hrs:.1f}hrs")

        return results

    async def run_and_store(self, robot_id: str = "go2_001") -> int:
        """
        Predict + SQLite mein store karo.
        APScheduler yeh call karega har 5 min.
        Returns: number of warnings/criticals found
        """
        print(f"[LSTM] Running prediction cycle...")
        predictions = await self.predict_all_joints(robot_id)

        alerts = 0
        for pred in predictions:
            await upsert_twin_forecast(
                joint_name    = pred["joint_name"],
                fail_in_hours = pred["fail_in_hours"],
                confidence    = pred["confidence"],
                severity      = pred["severity"],
                action        = pred["action"],
                robot_id      = robot_id,
            )
            if pred["severity"] != "ok":
                alerts += 1

        print(f"[LSTM] Cycle done — {len(predictions)} joints | {alerts} alerts")
        return alerts


# ── Singleton instance ──────────────────────────
_predictor: LSTMPredictor | None = None

def get_predictor() -> LSTMPredictor:
    global _predictor
    if _predictor is None:
        _predictor = LSTMPredictor()
    return _predictor
