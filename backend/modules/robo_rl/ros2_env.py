"""
NEXUS Phase 4 — RoboRL Step 3
ROS2 + Gazebo environment wrapper.

Inherits Go2Env (mock physics).
Overrides observations with real ROS2 sensor data.
Publishes actions to /cmd_vel.

Usage (MODE A only — Gazebo + ROS2 running):
    import rclpy
    from backend.modules.robo_rl.ros2_env import Go2ROS2Env
    rclpy.init()
    env = Go2ROS2Env()
    obs, info = env.reset()
"""

import numpy as np
import threading
import time
from typing import Optional, Tuple, Dict

# ROS2 imports — only available when ROS2 is sourced
try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan
    from std_srvs.srv import Empty
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False

from backend.modules.robo_rl.go2_env import Go2Env


class Go2ROS2Env(Go2Env):
    """
    ROS2-connected Gymnasium environment for Unitree Go2.

    Observation override:
        /odom  → robot_pos, robot_quat, robot_vel
        /scan  → lidar (12 rays sampled from full scan)

    Action execution:
        action → /cmd_vel (Twist message) at 10Hz

    Episode reset:
        Calls /reset_simulation service (Gazebo)
        Robot spawns at random position via /set_entity_state
    """

    LIDAR_RAYS   = 12          # rays we sample from full LiDAR scan
    CONTROL_HZ   = 10          # action publish rate
    SENSOR_TIMEOUT = 5.0       # seconds to wait for first sensor data

    def __init__(
        self,
        render_mode: Optional[str] = None,
        target_zone: Optional[str] = None,
        node_name: str = "go2_rl_env",
    ):
        if not ROS2_AVAILABLE:
            raise RuntimeError(
                "ROS2 not available. Source ROS2 before using Go2ROS2Env.\n"
                "  source /opt/ros/jazzy/setup.bash"
            )

        super().__init__(render_mode=render_mode, target_zone=target_zone)

        # ── ROS2 node ────────────────────────────────────────────────
        self._node = rclpy.create_node(node_name)

        qos_sensor = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        qos_reliable = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        # Publishers
        self._cmd_vel_pub = self._node.create_publisher(
            Twist, "/cmd_vel", qos_reliable
        )

        # Subscribers
        self._odom_sub = self._node.create_subscription(
            Odometry, "/odom", self._odom_callback, qos_sensor
        )
        self._scan_sub = self._node.create_subscription(
            LaserScan, "/scan", self._scan_callback, qos_sensor
        )

        # Service clients
        self._reset_client = self._node.create_client(Empty, "/reset_simulation")

        # Sensor data (thread-safe)
        self._lock       = threading.Lock()
        self._odom_ready = False
        self._scan_ready = False

        # Spin ROS2 in background thread
        self._spin_thread = threading.Thread(
            target=self._spin_ros2, daemon=True
        )
        self._spin_thread.start()

        self._node.get_logger().info("Go2ROS2Env initialized — waiting for sensors...")

    # ── ROS2 SPIN ───────────────────────────────────────────────────
    def _spin_ros2(self):
        """Background thread: keeps ROS2 callbacks alive."""
        rclpy.spin(self._node)

    # ── CALLBACKS ───────────────────────────────────────────────────
    def _odom_callback(self, msg: "Odometry"):
        with self._lock:
            pos = msg.pose.pose.position
            ori = msg.pose.pose.orientation
            vel = msg.twist.twist

            self._robot_pos = np.array(
                [pos.x, pos.y, pos.z], dtype=np.float32
            )
            self._robot_quat = np.array(
                [ori.x, ori.y, ori.z, ori.w], dtype=np.float32
            )
            self._robot_vel = np.array(
                [vel.linear.x, vel.angular.z], dtype=np.float32
            )
            self._odom_ready = True

    def _scan_callback(self, msg: "LaserScan"):
        """Sample 12 evenly-spaced rays from full LiDAR scan."""
        ranges   = np.array(msg.ranges, dtype=np.float32)
        n        = len(ranges)

        # Replace inf/nan with max range
        max_range = msg.range_max if msg.range_max > 0 else 5.0
        ranges    = np.where(np.isfinite(ranges), ranges, max_range)
        ranges    = np.clip(ranges, 0.0, 5.0)

        # Sample 12 evenly-spaced indices
        indices = np.linspace(0, n - 1, self.LIDAR_RAYS, dtype=int)

        with self._lock:
            self._lidar      = ranges[indices]
            self._scan_ready = True

    # ── RESET ───────────────────────────────────────────────────────
    def reset(self, *, seed=None, options=None) -> Tuple[np.ndarray, Dict]:
        """
        Reset episode:
        1. Call Gazebo /reset_simulation
        2. Wait for fresh sensor data
        3. Set random goal
        """
        import gymnasium as gym
        # Set numpy RNG via parent
        gym.Env.reset(self, seed=seed)

        # Call Gazebo reset service
        self._call_reset_service()

        # Choose goal zone
        if self.target_zone and self.target_zone in self.ZONES:
            self._goal_pos = self.ZONES[self.target_zone].copy()
        else:
            zone = self.np_random.choice(list(self.ZONES.keys()))
            self._goal_pos = self.ZONES[zone].copy()

        # Wait for fresh sensor data after reset
        self._wait_for_sensors()

        self._step_count = 0
        with self._lock:
            self._prev_dist = self._dist_to_goal()

        obs  = self._get_obs()
        info = {
            "goal_pos"  : self._goal_pos.copy(),
            "spawn_pos" : self._robot_pos.copy(),
            "source"    : "ros2",
        }
        return obs, info

    def _call_reset_service(self):
        """Call /reset_simulation service (Gazebo)."""
        if not self._reset_client.wait_for_service(timeout_sec=3.0):
            self._node.get_logger().warn(
                "/reset_simulation service not available — skipping reset"
            )
            return
        req = Empty.Request()
        future = self._reset_client.call_async(req)
        # Wait max 3s for response
        deadline = time.time() + 3.0
        while not future.done() and time.time() < deadline:
            time.sleep(0.05)

    def _wait_for_sensors(self):
        """Block until /odom and /scan have fresh data (or timeout)."""
        # Mark stale
        with self._lock:
            self._odom_ready = False
            self._scan_ready = False

        deadline = time.time() + self.SENSOR_TIMEOUT
        while time.time() < deadline:
            with self._lock:
                if self._odom_ready and self._scan_ready:
                    return
            time.sleep(0.05)

        self._node.get_logger().warn(
            "Sensor timeout — using last known values. "
            "Check Gazebo is running and topics are publishing."
        )

    # ── STEP ────────────────────────────────────────────────────────
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        1. Publish action to /cmd_vel
        2. Sleep 1/10Hz (let Gazebo simulate)
        3. Read fresh sensor data
        4. Compute reward using real robot state
        """
        action    = np.clip(action, self.action_space.low, self.action_space.high)
        linear_x  = float(action[0])
        angular_z = float(action[1])

        # Publish to Gazebo
        self._publish_cmd_vel(linear_x, angular_z)

        # Wait one control step for Gazebo to simulate
        time.sleep(1.0 / self.CONTROL_HZ)

        # Update velocity record (odom gives actual, this is commanded)
        with self._lock:
            self._robot_vel = np.array([linear_x, angular_z], dtype=np.float32)

        # Reward + termination (uses real _robot_pos from odom callback)
        reward, terminated = self._compute_reward()

        self._step_count += 1
        truncated = self._step_count >= self.MAX_STEPS

        with self._lock:
            self._prev_dist = self._dist_to_goal()

        obs  = self._get_obs()
        info = {
            "dist_to_goal"  : self._dist_to_goal(),
            "step"          : self._step_count,
            "collision"     : self._check_collision(),
            "boundary_viol" : self._check_boundary(),
            "source"        : "ros2",
        }
        return obs, reward, terminated, truncated, info

    def _publish_cmd_vel(self, linear_x: float, angular_z: float):
        """Publish Twist message to /cmd_vel."""
        msg             = Twist()
        msg.linear.x    = linear_x
        msg.angular.z   = angular_z
        self._cmd_vel_pub.publish(msg)

    # ── STOP ROBOT ──────────────────────────────────────────────────
    def stop_robot(self):
        """Send zero velocity — emergency stop."""
        self._publish_cmd_vel(0.0, 0.0)

    # ── CLOSE ───────────────────────────────────────────────────────
    def close(self):
        self.stop_robot()
        self._node.destroy_node()
        self._node.get_logger().info("Go2ROS2Env closed.")
