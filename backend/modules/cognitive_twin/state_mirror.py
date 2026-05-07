"""
state_mirror.py — ROS2 → SQLite bridge
Subscribes: /joint_states, /odom, /imu/data
Writes to SQLite every 500ms via asyncio
Runs IsolationForest anomaly check on every update
"""

import asyncio
import math
import time
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState, Imu
from nav_msgs.msg import Odometry
from sklearn.ensemble import IsolationForest
import numpy as np
import sys
from pathlib import Path

# Project root sys.path mein daalo
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.database.crud import (
    insert_robot_state,
    insert_joint_health,
    log_safety_event,
)

# ─── Joint name mapping ───────────────────────
# Go2 ke 12 joints — ROS2 /joint_states ka order
JOINT_NAMES = [
    "FR_hip", "FR_thigh", "FR_calf",
    "FL_hip", "FL_thigh", "FL_calf",
    "RR_hip", "RR_thigh", "RR_calf",
    "RL_hip", "RL_thigh", "RL_calf",
]

# ─── Health calculation ───────────────────────
# Simple heuristic: effort + temperature se health estimate
# LSTM baad mein yeh refine karega
def estimate_health(effort: float, temperature: float, vibration: float) -> float:
    """
    Rule-based health score (0-100%).
    Temporary — LSTM Step 4 mein replace karega.
    High effort + high temp + high vibration = low health.
    """
    effort_penalty  = min(abs(effort) / 20.0, 1.0) * 40   # max 40 points off
    temp_penalty    = max(0, (temperature - 50) / 50) * 30  # >50°C se penalty
    vibr_penalty    = min(vibration / 2.0, 1.0) * 30        # max 30 points off
    health = 100.0 - effort_penalty - temp_penalty - vibr_penalty
    return max(0.0, min(100.0, health))


# ─── Anomaly Detector ─────────────────────────
class AnomalyDetector:
    """
    IsolationForest — real-time spike detection.
    Warm-up: pehle 50 samples ke baad activate hota hai.
    Features: [effort, temperature, vibration] per joint
    """
    def __init__(self, contamination: float = 0.05):
        self.model = IsolationForest(
            contamination=contamination,  # 5% outliers expected
            random_state=42,
            n_estimators=50,              # RAM ke liye chhota rakhao
        )
        self.buffer = []          # training samples
        self.fitted  = False
        self.min_samples = 50     # itne samples ke baad fit karo

    def update(self, features: list[float]) -> bool:
        """
        features = [effort_0..11, temp_0..11, vibration]
        Returns True = anomaly detected
        """
        self.buffer.append(features)

        # Warm-up phase — pehle fit nahi karenge
        if len(self.buffer) < self.min_samples:
            return False

        # Har 10 samples pe refit (model fresh rehta hai)
        if len(self.buffer) % 10 == 0:
            X = np.array(self.buffer[-200:])  # last 200 only (RAM)
            self.model.fit(X)
            self.fitted = True

        if not self.fitted:
            return False

        score = self.model.predict([features])[0]
        return score == -1  # -1 = anomaly, 1 = normal


# ─── ROS2 Node ───────────────────────────────
class StateMirrorNode(Node):
    """
    ROS2 subscriber node.
    3 topics subscribe karta hai, data buffer mein rakhta hai.
    asyncio loop 500ms pe SQLite mein flush karta hai.
    """

    def __init__(self):
        super().__init__("state_mirror")

        # Latest data buffer — thread-safe nahi, but
        # rclpy spin_once single-threaded hai toh safe hai
        self._joint_data  = None   # JointState message
        self._odom_data   = None   # Odometry message
        self._imu_data    = None   # Imu message
        self._vib_history = []     # vibration magnitude history

        self.anomaly = AnomalyDetector()

        # Subscribers
        self.create_subscription(
            JointState, "/joint_states",
            self._on_joint_states, 10
        )
        self.create_subscription(
            Odometry, "/odom",
            self._on_odom, 10
        )
        self.create_subscription(
            Imu, "/imu/data",
            self._on_imu, 10
        )

        self.get_logger().info("[StateMirror] Subscribed to /joint_states, /odom, /imu/data")

    # ── Callbacks (just buffer, no DB calls here) ──

    def _on_joint_states(self, msg: JointState):
        self._joint_data = msg

    def _on_odom(self, msg: Odometry):
        self._odom_data = msg

    def _on_imu(self, msg: Imu):
        self._imu_data = msg
        # Vibration = IMU linear acceleration magnitude
        a = msg.linear_acceleration
        mag = math.sqrt(a.x**2 + a.y**2 + a.z**2)
        self._vib_history.append(mag)
        # Last 10 samples ka average rakhao
        if len(self._vib_history) > 10:
            self._vib_history.pop(0)

    # ── Getters ──

    def get_vibration(self) -> float:
        if not self._vib_history:
            return 0.0
        return sum(self._vib_history) / len(self._vib_history)

    def get_heading_deg(self) -> float:
        """Quaternion → degrees (yaw only)"""
        if not self._odom_data:
            return 0.0
        q = self._odom_data.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y**2 + q.z**2)
        return math.degrees(math.atan2(siny, cosy)) % 360


# ─── Async flush loop ─────────────────────────
async def flush_loop(node: StateMirrorNode, interval: float = 0.5):
    """
    Har 500ms — SINGLE batch transaction mein sab kuch likho.
    Fix: 13 connections → 1 connection, 1 commit.
    """
    from backend.database.crud import batch_flush
    print("[StateMirror] Flush loop started (500ms interval) [BATCH MODE]")

    while True:
        await asyncio.sleep(interval)

        # Koi data nahi toh skip
        if not node._joint_data and not node._odom_data:
            continue

        ts_start = time.time()

        # ── Robot state dict build karo ──
        robot_state_data = {"robot_id": "go2_001", "pos_x": 0.0, "pos_y": 0.0,
                            "pos_z": 0.0, "heading_deg": 0.0, "velocity": 0.0,
                            "gait": "stand", "mode": "idle"}
        if node._odom_data:
            p = node._odom_data.pose.pose.position
            t = node._odom_data.twist.twist.linear
            robot_state_data.update({
                "pos_x":       round(p.x, 4),
                "pos_y":       round(p.y, 4),
                "pos_z":       round(p.z, 4),
                "heading_deg": round(node.get_heading_deg(), 2),
                "velocity":    round(math.sqrt(t.x**2 + t.y**2), 4),
                "gait":        "trot",
                "mode":        "autonomous",
            })

        # ── Joint health list build karo ──
        joints_data = []
        if node._joint_data:
            msg       = node._joint_data
            vibration = node.get_vibration()
            efforts   = list(msg.effort) if msg.effort else [0.0] * 12
            temps     = [45.0 + abs(e) * 0.5 for e in efforts]

            # Anomaly check
            anomaly_features = efforts[:12] + temps[:12] + [vibration]
            if node.anomaly.update(anomaly_features):
                print(f"[StateMirror] ⚠️  ANOMALY at {time.strftime('%H:%M:%S')}")
                await log_safety_event("joint_anomaly","robot_body",0.0,"none",0.0,0.0,0)

            names = msg.name if msg.name else JOINT_NAMES
            for i, jname in enumerate(names[:12]):
                e = efforts[i] if i < len(efforts) else 0.0
                t = temps[i]
                joints_data.append({
                    "robot_id":   "go2_001",
                    "joint_name": jname,
                    "health_pct": round(estimate_health(e, t, vibration), 2),
                    "temperature":round(t, 2),
                    "vibration":  round(vibration, 4),
                    "current_a":  round(abs(e) * 0.1, 4),
                    "wear_rate":  round(abs(e) * 0.001, 6),
                })

        # ── Single batch write ──
        await batch_flush(robot_state_data, joints_data)

        elapsed = (time.time() - ts_start) * 1000
        print(f"[StateMirror] ✅ flush {elapsed:.1f}ms | joints={len(joints_data)}")


# ─── Entry point ─────────────────────────────
async def main():
    rclpy.init()
    node = StateMirrorNode()

    # ROS2 spin aur asyncio flush dono saath chalao
    loop = asyncio.get_event_loop()

    # ROS2 spin_once ko asyncio executor mein wrap karo
    async def ros_spin():
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.01)
            await asyncio.sleep(0.01)

    # Dono tasks concurrently chalao
    await asyncio.gather(
        ros_spin(),
        flush_loop(node),
    )

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
