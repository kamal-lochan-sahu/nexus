"""
Step 8: Navigation Executor
Converts VLA plan → /cmd_vel Twist messages → Go2 moves
Topic: /cmd_vel (already bridged in launch file)
"""
import time
import logging
import threading

logger = logging.getLogger(__name__)

# Lazy ROS2 import — only when needed
_ros_available = False
_publisher = None
_node = None

def _init_ros():
    global _ros_available, _publisher, _node
    if _ros_available:
        return True
    try:
        import rclpy
        from rclpy.node import Node
        from geometry_msgs.msg import Twist

        try:
            rclpy.init()
        except RuntimeError:
            pass  # already initialized

        class NavNode(Node):
            def __init__(self):
                super().__init__('vla_nav_executor')
                self.pub = self.create_publisher(Twist, '/cmd_vel', 10)

        _node = NavNode()
        _publisher = _node.pub
        _ros_available = True
        logger.info("Navigation executor: ROS2 ready, /cmd_vel publisher created")
        return True
    except Exception as e:
        logger.warning(f"ROS2 not available: {e} — simulation mode")
        return False

def execute_plan(vla_output: dict) -> dict:
    """
    Execute VLA plan via /cmd_vel.
    Returns execution status dict.
    """
    plan = vla_output.get("plan", [])
    intent = vla_output.get("intent", "unknown")
    safety = vla_output.get("safety_check", "unknown")

    if safety != "clear":
        logger.error(f"Safety not clear: {safety} — execution blocked")
        return {"status": "blocked", "reason": safety}

    ros_ok = _init_ros()
    results = []

    for step in plan:
        action = step.get("action")
        params = step.get("params", {})
        vel = params.get("velocity", 0.3)
        approach = params.get("approach_distance", 0.5)

        logger.info(f"Executing step {step.get('step')}: {action} vel={vel}")

        if action == "navigate":
            _publish_velocity(ros_ok, linear_x=vel, duration=2.0)
            results.append({"step": step.get("step"),
                            "action": action, "status": "executing",
                            "velocity": vel})

        elif action == "search":
            rotate = params.get("rotate_speed", 0.2)
            _publish_velocity(ros_ok, angular_z=rotate, duration=1.5)
            results.append({"step": step.get("step"),
                            "action": action, "status": "searching",
                            "rotate_speed": rotate})

        elif action == "stop":
            _publish_velocity(ros_ok, 0, 0, duration=0.5)
            results.append({"step": step.get("step"),
                            "action": action, "status": "stopped"})

    return {
        "status": "executed",
        "intent": intent,
        "steps_executed": len(results),
        "results": results,
        "ros2_active": ros_ok
    }

def _publish_velocity(ros_ok: bool, linear_x: float = 0.0,
                       angular_z: float = 0.0, duration: float = 1.0):
    """Publish Twist to /cmd_vel."""
    if ros_ok and _publisher is not None:
        try:
            from geometry_msgs.msg import Twist
            import rclpy
            msg = Twist()
            msg.linear.x = float(linear_x)
            msg.angular.z = float(angular_z)
            _publisher.publish(msg)
            import rclpy as _r; _r.spin_once(_node, timeout_sec=0.1)
            logger.info(f"  /cmd_vel published: lin={linear_x} ang={angular_z}")
        except Exception as e:
            logger.warning(f"  publish failed: {e}")
    else:
        logger.info(f"  [SIM] cmd_vel: lin={linear_x} ang={angular_z} dur={duration}s")
