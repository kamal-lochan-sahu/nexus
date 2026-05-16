"""
NEXUS Phase 4 — Step 6,7,8 Tests
No ROS2 needed — tests routing logic and interfaces only.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))


# ── Step 6: rl_policy_node structure ────────────────────────────────
def test_policy_node_importable():
    """rl_policy_node.py import without ROS2 crash."""
    import importlib.util
    path = os.path.join(os.path.dirname(__file__),
                        "../../../../ros2_ws/src/nexus_robot/nexus_robot/rl_policy_node.py")
    assert os.path.exists(path), f"File missing: {path}"

def test_policy_node_has_required_methods():
    """RLPolicyNode has all required methods."""
    path = os.path.join(os.path.dirname(__file__),
                        "../../../../ros2_ws/src/nexus_robot/nexus_robot/rl_policy_node.py")
    source = open(path).read()
    for method in ["_odom_cb", "_scan_cb", "_control_loop",
                   "_build_obs", "_publish_cmd", "_stop_robot"]:
        assert method in source, f"Missing method: {method}"

def test_policy_node_control_hz():
    """Control loop is 10Hz."""
    path = os.path.join(os.path.dirname(__file__),
                        "../../../../ros2_ws/src/nexus_robot/nexus_robot/rl_policy_node.py")
    source = open(path).read()
    assert "CONTROL_HZ     = 10" in source

def test_policy_node_goal_radius():
    """Goal radius is 0.3m."""
    path = os.path.join(os.path.dirname(__file__),
                        "../../../../ros2_ws/src/nexus_robot/nexus_robot/rl_policy_node.py")
    source = open(path).read()
    assert "GOAL_RADIUS    = 0.3" in source


# ── Step 7: policy_runner ────────────────────────────────────────────
def test_policy_runner_importable():
    from backend.modules.robo_rl.policy_runner import PolicyRunner
    assert PolicyRunner is not None

def test_policy_runner_has_methods():
    from backend.modules.robo_rl.policy_runner import PolicyRunner
    for m in ["start_rl_navigation", "stop_rl_navigation", "get_status"]:
        assert hasattr(PolicyRunner, m), f"Missing: {m}"

def test_policy_runner_zones():
    from backend.modules.robo_rl.policy_runner import PolicyRunner
    for zone in ["A", "B", "C", "D"]:
        assert zone in PolicyRunner.ZONES

def test_policy_runner_stop_when_not_active():
    from backend.modules.robo_rl.policy_runner import PolicyRunner
    runner = PolicyRunner()
    result = runner.stop_rl_navigation()
    assert result["status"] == "not_active"

def test_policy_runner_status():
    from backend.modules.robo_rl.policy_runner import PolicyRunner
    runner = PolicyRunner()
    status = runner.get_status()
    assert "active" in status
    assert "goal_reached" in status
    assert status["active"] is False


# ── Step 8: orchestrator routing ─────────────────────────────────────
def test_orchestrator_importable():
    from backend.core.orchestrator import Orchestrator
    assert Orchestrator is not None

def test_orchestrator_nav_detection():
    """Navigation keywords correctly detected."""
    from backend.core import orchestrator as O
    nav_commands = [
        "Navigate to zone A",
        "go to zone B",
        "move to zone C",
        "drive to zone D",
    ]
    non_nav = [
        "stop the robot",
        "turn left",
        "increase speed",
    ]
    orch = O.Orchestrator()
    for cmd in nav_commands:
        assert orch._is_navigation(cmd.lower()), f"Should be nav: {cmd}"
    for cmd in non_nav:
        assert not orch._is_navigation(cmd.lower()), f"Should not be nav: {cmd}"

def test_orchestrator_zone_extraction():
    """Zone A/B/C/D correctly extracted from command."""
    import re
    from backend.core.orchestrator import ZONE_PATTERN
    for zone in ["A", "B", "C", "D"]:
        cmd = f"Navigate to zone {zone}"
        match = ZONE_PATTERN.search(cmd)
        assert match is not None
        assert match.group(1).upper() == zone

def test_orchestrator_zone_coordinates():
    """Zone coordinates match spec."""
    from backend.core.orchestrator import ZONES
    assert ZONES["A"] == (-2.5,  2.5)
    assert ZONES["B"] == ( 2.5,  2.5)
    assert ZONES["C"] == (-2.5, -2.5)
    assert ZONES["D"] == ( 2.5, -2.5)

def test_orchestrator_routes_nav_to_robo_rl():
    """Navigation command routes to robo_rl module."""
    from backend.core.orchestrator import Orchestrator
    import unittest.mock as mock

    orch = Orchestrator()
    # Mock the runner so ROS2 not needed
    orch._rl_runner.start_rl_navigation = mock.MagicMock(
        return_value={"status": "started", "goal": (-2.5, 2.5), "pid": 1234}
    )
    result = orch.handle("Navigate to zone A")
    assert result["module"] == "robo_rl"
    assert result["zone"]   == "A"
    assert result["goal"]   == (-2.5, 2.5)

def test_orchestrator_routes_direct_to_nl2rc():
    """Direct command routes to nl2rc module."""
    from backend.core.orchestrator import Orchestrator
    orch   = Orchestrator()
    result = orch.handle("turn left 90 degrees")
    assert result["module"] == "nl2rc"
