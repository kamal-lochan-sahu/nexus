"""
NEXUS Phase 4 — Step 7
Policy Runner — Python interface to rl_policy_node.

Usage:
    from backend.modules.robo_rl.policy_runner import PolicyRunner
    runner = PolicyRunner()
    runner.start_rl_navigation(goal_x=-2.5, goal_y=2.5)
    runner.stop_rl_navigation()
"""

import subprocess
import threading
import time
import os
from typing import Optional


class PolicyRunner:
    """
    Manages rl_policy_node lifecycle.
    start_rl_navigation() → launches ROS2 node
    stop_rl_navigation()  → kills node, returns control to NL2RC
    """

    POLICY_PATH = os.path.join(
        os.path.dirname(__file__),
        "../../../models/ppo_go2/best_model.zip"
    )

    ZONES = {
        "A": (-2.5,  2.5),
        "B": ( 2.5,  2.5),
        "C": (-2.5, -2.5),
        "D": ( 2.5, -2.5),
    }

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._active  = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._goal_reached = False

    # ── START ────────────────────────────────────────────────────────
    def start_rl_navigation(
        self,
        goal_x: float = 2.5,
        goal_y: float = 2.5,
        zone:   str   = "",
    ) -> dict:
        """
        Launch rl_policy_node with given goal.
        Returns immediately — node runs in background.
        """
        if self._active:
            return {"status": "already_active", "goal": (goal_x, goal_y)}

        # Zone override
        if zone.upper() in self.ZONES:
            goal_x, goal_y = self.ZONES[zone.upper()]

        cmd = [
            "ros2", "run", "nexus_robot", "rl_policy_node",
            "--ros-args",
            "-p", f"goal_x:={goal_x}",
            "-p", f"goal_y:={goal_y}",
            "-p", f"policy_path:={self.POLICY_PATH}",
        ]

        self._goal_reached = False
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            print("[NEXUS] ROS2 binary not found — RL navigation unavailable")
            return {"status": "unavailable", "message": "ros2 not found"}
        self._active = True

        # Monitor thread — watches for goal reached / crash
        self._monitor_thread = threading.Thread(
            target=self._monitor, daemon=True
        )
        self._monitor_thread.start()

        return {
            "status"  : "started",
            "goal"    : (goal_x, goal_y),
            "pid"     : self._process.pid,
        }

    # ── STOP ─────────────────────────────────────────────────────────
    def stop_rl_navigation(self) -> dict:
        """
        Stop rl_policy_node. Robot stops, control returns.
        """
        if not self._active or self._process is None:
            return {"status": "not_active"}

        self._process.terminate()
        try:
            self._process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            self._process.kill()

        self._active       = False
        self._process      = None

        return {
            "status"       : "stopped",
            "goal_reached" : self._goal_reached,
        }

    # ── STATUS ───────────────────────────────────────────────────────
    def get_status(self) -> dict:
        return {
            "active"       : self._active,
            "goal_reached" : self._goal_reached,
            "pid"          : self._process.pid if self._process else None,
        }

    # ── MONITOR ──────────────────────────────────────────────────────
    def _monitor(self):
        """Background thread: watch node output for goal reached."""
        if self._process is None:
            return
        for line in self._process.stdout:
            text = line.decode("utf-8", errors="ignore").strip()
            if "GOAL REACHED" in text:
                self._goal_reached = True
                self._active       = False
                break
            if not self._active:
                break
