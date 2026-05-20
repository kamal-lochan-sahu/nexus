"""
NEXUS Phase 4 — Step 8
Orchestrator — routes commands to correct module.

Routing logic:
  has visual reference? → EmbodiedGPT  (future)
  multi-robot task?     → FlexCell     (future)
  autonomous nav?       → RoboRL       ← this phase
  direct command?       → NL2RC
"""

import re
from typing import Dict, Any


# Navigation keywords → RoboRL
# Multi-robot keywords → FlexCell
FLEET_KEYWORDS = [
    "patrol", "both robots", "all robots", "fleet",
    "coordinate", "inspect zone", "guard zone",
    "entire floor", "factory floor",
]

NAV_KEYWORDS = [
    "navigate", "go to", "move to", "head to",
    "drive to", "travel to", "reach", "proceed to",
]

# Zone pattern: "zone A/B/C/D"
ZONE_PATTERN = re.compile(r"\bzone\s+([ABCD])\b", re.IGNORECASE)

# Zone coordinate map
ZONES: Dict[str, tuple] = {
    "A": (-2.5,  2.5),
    "B": ( 2.5,  2.5),
    "C": (-2.5, -2.5),
    "D": ( 2.5, -2.5),
}


class Orchestrator:
    """
    Routes natural language commands to correct module.

    Example:
        orch = Orchestrator()
        result = orch.handle("Navigate to zone A")
        # → {"module": "robo_rl", "action": "navigate", "zone": "A", ...}
    """

    def __init__(self):
        from modules.robo_rl.policy_runner import PolicyRunner
        self._rl_runner = PolicyRunner()
        self._active_module = None

    def handle(self, command: str) -> Dict[str, Any]:
        """
        Parse command and route to correct module.
        Returns result dict with module, action, status.
        """
        cmd_lower = command.lower().strip()

        # ── Route: multi-robot task → FlexCell ─────────────────────
        if self._is_fleet_task(cmd_lower):
            return self._handle_fleet(command)

        # ── Route: autonomous navigation → RoboRL ───────────────────
        if self._is_navigation(cmd_lower):
            return self._handle_navigation(command)

        # ── Route: direct robot command → NL2RC ─────────────────────
        return self._handle_nl2rc(command)

    # ── NAVIGATION (RoboRL) ──────────────────────────────────────────
    
    # ── FLEET (FlexCell) ────────────────────────────────────────────
    def _is_fleet_task(self, cmd: str) -> bool:
        return any(kw in cmd for kw in FLEET_KEYWORDS)

    def _handle_fleet(self, command: str) -> Dict[str, Any]:
        return {
            "module": "flexcell",
            "action": "decompose",
            "goal":   command,
            "status": "queued",
        }

def _is_navigation(self, cmd: str) -> bool:
        return any(kw in cmd for kw in NAV_KEYWORDS)

    def _handle_navigation(self, command: str) -> Dict[str, Any]:
        # Extract zone
        zone_match = ZONE_PATTERN.search(command)
        zone = zone_match.group(1).upper() if zone_match else ""

        if zone in ZONES:
            goal_x, goal_y = ZONES[zone]
        else:
            # Default: zone B
            zone   = "B"
            goal_x, goal_y = ZONES["B"]

        # Stop any active navigation first
        if self._active_module == "robo_rl":
            self._rl_runner.stop_rl_navigation()

        result = self._rl_runner.start_rl_navigation(
            goal_x=goal_x,
            goal_y=goal_y,
            zone=zone,
        )
        self._active_module = "robo_rl"

        return {
            "module"  : "robo_rl",
            "action"  : "navigate",
            "zone"    : zone,
            "goal"    : (goal_x, goal_y),
            "status"  : result["status"],
            "message" : f"RL policy navigating to Zone {zone} ({goal_x}, {goal_y})",
        }

    # ── DIRECT COMMAND (NL2RC) ───────────────────────────────────────
    def _handle_nl2rc(self, command: str) -> Dict[str, Any]:
        # Stop RL if active
        if self._active_module == "robo_rl":
            self._rl_runner.stop_rl_navigation()
            self._active_module = None

        # Import NL2RC pipeline (Phase 1)
        try:
            from modules.nl2rc.pipeline import NL2RCPipeline
            pipeline = NL2RCPipeline()
            result   = pipeline.run(command)
            return {
                "module" : "nl2rc",
                "action" : "direct_command",
                "result" : result,
                "status" : "executed",
            }
        except ImportError:
            return {
                "module"  : "nl2rc",
                "action"  : "direct_command",
                "status"  : "nl2rc_unavailable",
                "message" : command,
            }

    # ── RL STATUS ────────────────────────────────────────────────────
    def get_rl_status(self) -> Dict[str, Any]:
        return self._rl_runner.get_status()

    def stop_all(self):
        """Emergency stop — all modules."""
        self._rl_runner.stop_rl_navigation()
        self._active_module = None
