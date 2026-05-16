"""
NEXUS Phase 4 — Step 6
ROS2 RL Policy Deployment Node.

Loads trained PPO policy, subscribes to /odom + /scan,
publishes /cmd_vel at 10Hz.

Usage:
    ros2 run nexus_robot rl_policy_node --ros-args -p goal_x:=-2.5 -p goal_y:=2.5
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool

import numpy as np
import threading
import time
import os

try:
    from stable_baselines3 import PPO
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False


class RLPolicyNode(Node):
    """
    Loads PPO policy.zip and runs inference at 10Hz.
    Subscribes : /odom, /scan
    Publishes  : /cmd_vel, /rl/active, /rl/goal_reached
    Parameters : goal_x, goal_y, policy_path
    """

    CONTROL_HZ     = 10
    GOAL_RADIUS    = 0.3
    ARENA_LIMIT    = 3.0
    LIDAR_RAYS     = 12
    LIDAR_MAX_DIST = 5.0

    ZONES = {
        "A": (-2.5,  2.5),
        "B": ( 2.5,  2.5),
        "C": (-2.5, -2.5),
        "D": ( 2.5, -2.5),
    }

    def __init__(self):
        super().__init__("rl_policy_node")

        # ── Parameters ──────────────────────────────────────────────
        self.declare_parameter("goal_x",       2.5)
        self.declare_parameter("goal_y",       2.5)
        self.declare_parameter("goal_zone",    "")   # "A/B/C/D" overrides x,y
        self.declare_parameter("policy_path",
            os.path.join(os.path.dirname(__file__),
                         "../../../../../../models/ppo_go2/best_model.zip"))
        self.declare_parameter("active", False)

        # ── State ───────────────────────────────────────────────────
        self._robot_pos  = np.zeros(3, dtype=np.float32)
        self._robot_quat = np.array([0., 0., 0., 1.], dtype=np.float32)
        self._robot_vel  = np.zeros(2, dtype=np.float32)
        self._lidar      = np.ones(self.LIDAR_RAYS, dtype=np.float32) * self.LIDAR_MAX_DIST
        self._goal_pos   = np.zeros(3, dtype=np.float32)
        self._active     = False
        self._lock       = threading.Lock()
        self._policy     = None

        # ── QoS ─────────────────────────────────────────────────────
        qos_sensor = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST, depth=1)
        qos_rel = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST, depth=1)

        # ── Subscribers ─────────────────────────────────────────────
        self.create_subscription(Odometry,   "/odom",    self._odom_cb,  qos_sensor)
        self.create_subscription(LaserScan,  "/scan",    self._scan_cb,  qos_sensor)
        self.create_subscription(Bool,       "/rl/activate", self._activate_cb, qos_rel)

        # ── Publishers ──────────────────────────────────────────────
        self._cmd_pub    = self.create_publisher(Twist, "/cmd_vel",       qos_rel)
        self._active_pub = self.create_publisher(Bool,  "/rl/active",     qos_rel)
        self._goal_pub   = self.create_publisher(Bool,  "/rl/goal_reached", qos_rel)

        # ── Control timer (10Hz) ────────────────────────────────────
        self.create_timer(1.0 / self.CONTROL_HZ, self._control_loop)

        # ── Load policy ─────────────────────────────────────────────
        self._load_policy()
        self._set_goal()

        self.get_logger().info("RLPolicyNode ready.")
        self.get_logger().info(f"  Goal: ({self._goal_pos[0]:.2f}, {self._goal_pos[1]:.2f})")
        self.get_logger().info("  Send True to /rl/activate to start.")

    # ── POLICY LOAD ─────────────────────────────────────────────────
    def _load_policy(self):
        if not SB3_AVAILABLE:
            self.get_logger().error("stable_baselines3 not installed!")
            return
        path = self.get_parameter("policy_path").value
        if not os.path.exists(path):
            self.get_logger().error(f"Policy not found: {path}")
            return
        import torch
        with torch.no_grad():
            self._policy = PPO.load(path, device="cpu")
        self.get_logger().info(f"✅ Policy loaded: {path}")

    # ── GOAL SETUP ──────────────────────────────────────────────────
    def _set_goal(self):
        zone = self.get_parameter("goal_zone").value.upper()
        if zone in self.ZONES:
            x, y = self.ZONES[zone]
            self.get_logger().info(f"Zone {zone} → goal ({x}, {y})")
        else:
            x = self.get_parameter("goal_x").value
            y = self.get_parameter("goal_y").value
        self._goal_pos = np.array([x, y, 0.0], dtype=np.float32)

    # ── CALLBACKS ───────────────────────────────────────────────────
    def _odom_cb(self, msg: Odometry):
        with self._lock:
            p = msg.pose.pose.position
            o = msg.pose.pose.orientation
            v = msg.twist.twist
            self._robot_pos  = np.array([p.x, p.y, p.z], dtype=np.float32)
            self._robot_quat = np.array([o.x, o.y, o.z, o.w], dtype=np.float32)
            self._robot_vel  = np.array([v.linear.x, v.angular.z], dtype=np.float32)

    def _scan_cb(self, msg: LaserScan):
        ranges = np.array(msg.ranges, dtype=np.float32)
        max_r  = msg.range_max if msg.range_max > 0 else self.LIDAR_MAX_DIST
        ranges = np.where(np.isfinite(ranges), ranges, max_r)
        ranges = np.clip(ranges, 0.0, self.LIDAR_MAX_DIST)
        idx    = np.linspace(0, len(ranges)-1, self.LIDAR_RAYS, dtype=int)
        with self._lock:
            self._lidar = ranges[idx]

    def _activate_cb(self, msg: Bool):
        with self._lock:
            self._active = msg.data
        state = "ACTIVATED" if msg.data else "DEACTIVATED"
        self.get_logger().info(f"RL policy {state}")
        if not msg.data:
            self._stop_robot()

    # ── CONTROL LOOP (10Hz) ─────────────────────────────────────────
    def _control_loop(self):
        if not self._active or self._policy is None:
            return

        obs = self._build_obs()

        import torch
        with torch.no_grad():
            action, _ = self._policy.predict(obs, deterministic=True)

        linear_x  = float(np.clip(action[0], 0.0,  0.5))
        angular_z = float(np.clip(action[1], -1.0,  1.0))
        self._publish_cmd(linear_x, angular_z)

        # Goal check
        dist = float(np.linalg.norm(self._robot_pos[:2] - self._goal_pos[:2]))
        if dist < self.GOAL_RADIUS:
            self.get_logger().info(f"🎯 GOAL REACHED! dist={dist:.3f}m")
            self._stop_robot()
            with self._lock:
                self._active = False
            msg = Bool(); msg.data = True
            self._goal_pub.publish(msg)

        # Publish active status
        status = Bool(); status.data = self._active
        self._active_pub.publish(status)

    # ── OBSERVATION BUILDER ─────────────────────────────────────────
    def _build_obs(self) -> np.ndarray:
        with self._lock:
            pos  = self._robot_pos.copy()
            quat = self._robot_quat.copy()
            vel  = self._robot_vel.copy()
            lidar = self._lidar.copy()

        goal_vec  = self._goal_pos - pos
        goal_dist = np.linalg.norm(goal_vec) + 1e-8
        goal_dir  = (goal_vec / goal_dist).astype(np.float32)

        obs = np.concatenate([pos, quat, goal_dir, lidar, vel]).astype(np.float32)
        return obs

    # ── HELPERS ─────────────────────────────────────────────────────
    def _publish_cmd(self, lx: float, az: float):
        msg = Twist()
        msg.linear.x  = lx
        msg.angular.z = az
        self._cmd_pub.publish(msg)

    def _stop_robot(self):
        self._publish_cmd(0.0, 0.0)


def main(args=None):
    rclpy.init(args=args)
    node = RLPolicyNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._stop_robot()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
