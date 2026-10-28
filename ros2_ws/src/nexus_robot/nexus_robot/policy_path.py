"""
policy_path.py - find the trained PPO policy without a hardcoded relative path.

Kept free of ROS imports so it can be unit-tested anywhere.

Order:
  1. the `policy_path` ROS parameter, if given
  2. the NEXUS_POLICY_PATH environment variable
  3. models/ppo_go2/best_model.zip in a parent folder of this file (source tree)
  4. models/ppo_go2/best_model.zip in a parent folder of the current directory

A path that was given explicitly but does not exist is an error (None), never silently replaced.
"""
import os
from pathlib import Path
from typing import Optional

RELATIVE_POLICY = Path("models") / "ppo_go2" / "best_model.zip"
ENV_VAR = "NEXUS_POLICY_PATH"
MAX_PARENTS = 8


def _search_upwards(start: Path) -> Optional[Path]:
    start = start.resolve()
    for folder in [start, *list(start.parents)[:MAX_PARENTS]]:
        candidate = folder / RELATIVE_POLICY
        if candidate.is_file():
            return candidate
    return None


def find_policy(explicit: str = "", *, module_file: str = __file__, cwd: Optional[str] = None) -> Optional[str]:
    for given in (explicit, os.environ.get(ENV_VAR, "")):
        given = (given or "").strip()
        if given:
            path = Path(given).expanduser()
            return str(path) if path.is_file() else None

    for start in (Path(module_file).parent, Path(cwd or os.getcwd())):
        found = _search_upwards(start)
        if found is not None:
            return str(found)
    return None
