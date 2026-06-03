"""
NEXUS Phase 8 — Step 1
Orchestrator — routes commands to all 6 modules.

Routing priority:
  1. visual reference?   → EmbodiedGPT
  2. multi-robot task?   → FlexCell
  3. autonomous nav?     → RoboRL
  4. direct command?     → NL2RC
"""

import re
from typing import Dict, Any


# ── Keyword Banks ────────────────────────────────────────────────────

VISUAL_KEYWORDS = [
    "inspect", "look at", "analyze", "identify", "detect",
    "yellow", "red", "blue", "marker", "what is", "what's",
    "scan", "examine", "check marker", "vision", "see",
]

FLEET_KEYWORDS = [
    "patrol", "both robots", "all robots", "fleet",
    "coordinate", "inspect zone", "guard zone",
    "entire floor", "factory floor", "full factory",
]

NAV_KEYWORDS = [
    "navigate", "go to", "move to", "head to",
    "drive to", "travel to", "reach", "proceed to",
    "autonomous", "auto patrol", "enable patrol",
]

ZONE_PATTERN = re.compile(r"\bzone\s+([ABCD])\b", re.IGNORECASE)

ZONES: Dict[str, tuple] = {
    "A": (-2.5,  2.5),
    "B": ( 2.5,  2.5),
    "C": (-2.5, -2.5),
    "D": ( 2.5, -2.5),
}


class Orchestrator:
    """
    Routes natural language commands to correct module.

    Priority: EmbodiedGPT > FlexCell > RoboRL > NL2RC
    """

    def __init__(self):
        from modules.robo_rl.policy_runner import PolicyRunner
        self._rl_runner = PolicyRunner()
        self._active_module = None

    def handle(self, command: str) -> Dict[str, Any]:
        cmd_lower = command.lower().strip()

        # ── Route 1: visual reference → EmbodiedGPT ─────────────────
        if self._is_visual_task(cmd_lower):
            return self._handle_embodied(command)

        # ── Route 2: autonomous navigation → RoboRL ─────────────────
        if self._is_navigation(cmd_lower):
            return self._handle_navigation(command)

        # ── Route 3: multi-robot task → FlexCell ─────────────────────
        if self._is_fleet_task(cmd_lower):
            return self._handle_fleet(command)

        # ── Route 4: direct command → NL2RC ─────────────────────────
        return self._handle_nl2rc(command)

    # ── VISUAL (EmbodiedGPT) ─────────────────────────────────────────

    def _is_visual_task(self, cmd: str) -> bool:
        return any(kw in cmd for kw in VISUAL_KEYWORDS)

    def _handle_embodied(self, command: str) -> Dict[str, Any]:
        try:
            from modules.embodied_gpt.vla_pipeline import VLAPipeline
            pipeline = VLAPipeline()
            result = pipeline.run(command)
            self._active_module = "embodied_gpt"
            return {
                "module": "embodied_gpt",
                "action": "vla_pipeline",
                "command": command,
                "result": result,
                "status": "executed",
            }
        except Exception as e:
            return {
                "module": "embodied_gpt",
                "action": "vla_pipeline",
                "status": "unavailable",
                "message": str(e),
            }

    # ── FLEET (FlexCell) ─────────────────────────────────────────────

    def _is_fleet_task(self, cmd: str) -> bool:
        return any(kw in cmd for kw in FLEET_KEYWORDS)

    def _handle_fleet(self, command: str) -> Dict[str, Any]:
        try:
            from modules.flexcell.task_decomposer import TaskDecomposer
            decomposer = TaskDecomposer()
            result = decomposer.decompose(command)
            self._active_module = "flexcell"
            return {
                "module": "flexcell",
                "action": "decompose",
                "goal": command,
                "tasks": result,
                "status": "queued",
            }
        except Exception as e:
            return {
                "module": "flexcell",
                "action": "decompose",
                "goal": command,
                "status": "queued",
                "message": str(e),
            }

    # ── NAVIGATION (RoboRL) ──────────────────────────────────────────

    def _is_navigation(self, cmd: str) -> bool:
        return any(kw in cmd for kw in NAV_KEYWORDS)

    def _handle_navigation(self, command: str) -> Dict[str, Any]:
        zone_match = ZONE_PATTERN.search(command)
        zone = zone_match.group(1).upper() if zone_match else "B"
        goal_x, goal_y = ZONES.get(zone, ZONES["B"])

        if self._active_module == "robo_rl":
            self._rl_runner.stop_rl_navigation()

        result = self._rl_runner.start_rl_navigation(
            goal_x=goal_x,
            goal_y=goal_y,
            zone=zone,
        )
        self._active_module = "robo_rl"

        return {
            "module": "robo_rl",
            "action": "navigate",
            "zone": zone,
            "goal": (goal_x, goal_y),
            "status": result["status"],
            "message": f"RL policy navigating to Zone {zone} ({goal_x}, {goal_y})",
        }

    # ── DIRECT COMMAND (NL2RC) ───────────────────────────────────────

    def _handle_nl2rc(self, command: str) -> Dict[str, Any]:
        if self._active_module == "robo_rl":
            self._rl_runner.stop_rl_navigation()
            self._active_module = None

        try:
            from modules.nl2rc.pipeline import NL2RCPipeline
            pipeline = NL2RCPipeline()
            result = pipeline.run(command)
            self._active_module = "nl2rc"
            return {
                "module": "nl2rc",
                "action": "direct_command",
                "result": result,
                "status": "executed",
            }
        except Exception as e:
            return {
                "module": "nl2rc",
                "action": "direct_command",
                "status": "unavailable",
                "message": str(e),
            }

    # ── UTILITIES ────────────────────────────────────────────────────

    def get_rl_status(self) -> Dict[str, Any]:
        return self._rl_runner.get_status()

    def stop_all(self):
        """Emergency stop — all modules."""
        self._rl_runner.stop_rl_navigation()
        self._active_module = None
        return {"status": "stopped", "message": "All modules halted"}
