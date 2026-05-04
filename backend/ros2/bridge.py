"""
bridge.py — rosbridge WebSocket client
FastAPI → rosbridge (:9090) → ROS2 → Go2 robot
"""
import json
import threading
import time
import websocket  # websocket-client library


class RosBridge:
    """
    Rosbridge ke saath ek persistent connection maintain karta hai.
    Thread-safe hai — multiple async calls simultaneously safe hain.
    """

    def __init__(self, url: str = "ws://localhost:9090"):
        self.url = url
        self.ws = None
        self._lock = threading.Lock()  # Thread safety ke liye
        self._connected = False

    # ── Connection ────────────────────────────────────────────────
    def connect(self) -> bool:
        """Rosbridge se connect karo. True = success, False = fail."""
        try:
            self.ws = websocket.create_connection(self.url, timeout=5)
            self._connected = True
            print(f"[Bridge] Connected to rosbridge at {self.url}")
            return True
        except Exception as e:
            self._connected = False
            print(f"[Bridge] Connection failed: {e}")
            return False

    def disconnect(self):
        """Connection cleanly band karo."""
        if self.ws:
            self.ws.close()
        self._connected = False
        print("[Bridge] Disconnected from rosbridge")

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Publisher ─────────────────────────────────────────────────
    def publish(self, topic: str, msg_type: str, data: dict) -> bool:
        """
        Koi bhi ROS2 topic pe message publish karo.
        rosbridge ka standard JSON format use karta hai.
        """
        if not self._connected:
            print("[Bridge] Not connected — cannot publish")
            return False

        # Rosbridge ka exact message format
        message = {
            "op": "publish",
            "topic": topic,
            "type": msg_type,
            "msg": data,
        }

        with self._lock:  # Ek waqt mein sirf ek thread publish kare
            try:
                self.ws.send(json.dumps(message))
                return True
            except Exception as e:
                self._connected = False
                print(f"[Bridge] Publish failed: {e}")
                return False

    # ── cmd_vel shortcut ──────────────────────────────────────────
    def send_cmd_vel(
        self,
        robot_id: str = "go2_a",
        linear_x: float = 0.0,
        angular_z: float = 0.0,
    ) -> bool:
        """
        Go2 robot ko velocity command bhejo.
        robot_id: "go2_a" ya "go2_b"
        linear_x: forward speed (max 0.5 m/s — safety limit)
        angular_z: rotation speed (max 1.0 rad/s — safety limit)
        """
        # Safety limits — hardcoded, override nahi ho sakti
        linear_x  = max(-0.5, min(0.5, linear_x))
        angular_z = max(-1.0, min(1.0, angular_z))

        topic = f"/{robot_id}/cmd_vel"

        data = {
            "linear":  {"x": linear_x,  "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": angular_z},
        }

        success = self.publish(
            topic=topic,
            msg_type="geometry_msgs/Twist",
            data=data,
        )

        if success:
            print(f"[Bridge] cmd_vel → {topic} | "
                  f"linear_x={linear_x} angular_z={angular_z}")
        return success

    def stop_robot(self, robot_id: str = "go2_a") -> bool:
        """Emergency stop — zero velocity publish karo."""
        return self.send_cmd_vel(robot_id=robot_id,
                                 linear_x=0.0, angular_z=0.0)


# ── Singleton instance ────────────────────────────────────────────
# Poore backend mein ek hi bridge instance use hoga
ros_bridge = RosBridge(url="ws://localhost:9090")
