"""
NEXUS Phase 4 — Step 3
Smoke test: ROS2 env wrapper import + structure check.
No Gazebo needed — just verifies class hierarchy + interface.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))


def test_ros2_env_import():
    """ros2_env.py import hona chahiye without crashing."""
    from backend.modules.robo_rl import ros2_env
    assert hasattr(ros2_env, "Go2ROS2Env")


def test_ros2_env_inherits_go2env():
    """Go2ROS2Env must inherit Go2Env."""
    from backend.modules.robo_rl.ros2_env import Go2ROS2Env
    from backend.modules.robo_rl.go2_env import Go2Env
    assert issubclass(Go2ROS2Env, Go2Env)


def test_ros2_env_no_ros2_raises():
    """Without ROS2, instantiation raises RuntimeError."""
    import unittest.mock as mock
    import importlib

    # Temporarily make rclpy unavailable
    with mock.patch.dict("sys.modules", {"rclpy": None, "rclpy.node": None}):
        import backend.modules.robo_rl.ros2_env as m
        import importlib
        importlib.reload(m)

        try:
            env = m.Go2ROS2Env()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "ROS2 not available" in str(e)


def test_ros2_env_has_required_methods():
    """All required methods exist on Go2ROS2Env."""
    from backend.modules.robo_rl.ros2_env import Go2ROS2Env
    for method in ["reset", "step", "close", "stop_robot",
                   "_odom_callback", "_scan_callback", "_publish_cmd_vel"]:
        assert hasattr(Go2ROS2Env, method), f"Missing method: {method}"


def test_ros2_env_constants():
    """Control constants are correct."""
    from backend.modules.robo_rl.ros2_env import Go2ROS2Env
    assert Go2ROS2Env.LIDAR_RAYS   == 12
    assert Go2ROS2Env.CONTROL_HZ   == 10
    assert Go2ROS2Env.SENSOR_TIMEOUT == 5.0
