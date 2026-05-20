"""
FlexCell — Step 4: Fleet ROS2 Node
Manages Go2-A and Go2-B via separate namespaces.
/go2_a/cmd_vel + /go2_b/cmd_vel
/go2_a/odom   + /go2_b/odom
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import math


ZONE_WAYPOINTS = {
    "A": [(-2.5, 2.5), (-1.5, 2.5), (-0.5, 2.5),
          (-2.5, 1.5), (-1.5, 1.5), (-0.5, 1.5)],
    "B": [(0.5, 2.5),  (1.5, 2.5),  (2.5, 2.5),
          (0.5, 1.5),  (1.5, 1.5),  (2.5, 1.5)],
    "C": [(-2.5,-0.5), (-1.5,-0.5), (-0.5,-0.5),
          (-2.5,-1.5), (-1.5,-1.5), (-0.5,-1.5)],
    "D": [(0.5,-0.5),  (1.5,-0.5),  (2.5,-0.5),
          (0.5,-1.5),  (1.5,-1.5),  (2.5,-1.5)],
}

PATROL_SPEED  = 0.3   # m/s
TURN_SPEED    = 0.5   # rad/s
GOAL_TOLERANCE= 0.3   # m


class RobotController:
    """Single robot controller — holds its own state."""

    def __init__(self, node: Node, robot_id: str):
        self.node      = node
        self.robot_id  = robot_id
        self.pos_x     = 0.0
        self.pos_y     = 0.0
        self.yaw       = 0.0
        self.paused    = False
        self.waypoints: list[tuple] = []
        self.wp_idx    = 0

        ns = f"/{robot_id}"
        self.cmd_pub = node.create_publisher(Twist, f"{ns}/cmd_vel", 10)
        node.create_subscription(
            Odometry, f"{ns}/odom", self._odom_cb, 10
        )

    def _odom_cb(self, msg: Odometry) -> None:
        self.pos_x = msg.pose.pose.position.x
        self.pos_y = msg.pose.pose.position.y
        # Extract yaw from quaternion
        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.yaw = math.atan2(siny, cosy)

    def set_patrol_zone(self, zone: str) -> None:
        self.waypoints = ZONE_WAYPOINTS.get(zone, [])
        self.wp_idx    = 0
        self.node.get_logger().info(
            f"{self.robot_id}: Patrol zone {zone} — {len(self.waypoints)} waypoints"
        )

    def stop(self) -> None:
        self.cmd_pub.publish(Twist())

    def patrol_step(self) -> None:
        """Called every 100ms by timer."""
        if self.paused or not self.waypoints:
            self.stop()
            return

        if self.wp_idx >= len(self.waypoints):
            self.wp_idx = 0   # Loop patrol

        gx, gy  = self.waypoints[self.wp_idx]
        dx      = gx - self.pos_x
        dy      = gy - self.pos_y
        dist    = math.sqrt(dx*dx + dy*dy)

        if dist < GOAL_TOLERANCE:
            self.wp_idx += 1
            self.stop()
            return

        # Heading toward goal
        target_yaw = math.atan2(dy, dx)
        yaw_err    = target_yaw - self.yaw
        # Normalize to [-pi, pi]
        while yaw_err >  math.pi: yaw_err -= 2*math.pi
        while yaw_err < -math.pi: yaw_err += 2*math.pi

        cmd = Twist()
        if abs(yaw_err) > 0.2:
            cmd.angular.z = TURN_SPEED * (1 if yaw_err > 0 else -1)
        else:
            cmd.linear.x  = PATROL_SPEED
            cmd.angular.z = 0.3 * yaw_err

        self.cmd_pub.publish(cmd)


class FleetNode(Node):
    def __init__(self):
        super().__init__("fleet_node")
        self.get_logger().info("FleetNode starting...")

        self.go2_a = RobotController(self, "go2_a")
        self.go2_b = RobotController(self, "go2_b")

        # Default patrol zones
        self.go2_a.set_patrol_zone("A")
        self.go2_b.set_patrol_zone("C")

        # 100ms control loop
        self.create_timer(0.1, self._control_loop)
        self.get_logger().info("FleetNode ready. Go2-A→ZoneA, Go2-B→ZoneC")

    def _control_loop(self) -> None:
        self.go2_a.patrol_step()
        self.go2_b.patrol_step()


def main(args=None):
    rclpy.init(args=args)
    node = FleetNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.go2_a.stop()
        node.go2_b.stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
