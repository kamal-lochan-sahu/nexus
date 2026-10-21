"""
auth.py - optional API-key protection for the endpoints that change state or cost money.

  NEXUS_API_KEY set    -> protected endpoints need the header  X-API-Key: <key>
  NEXUS_API_KEY unset  -> auth is OFF (local development); main.py prints a warning at startup

Protected: POST /command, POST /flexcell/task, POST /flexcell/robot/{id}/pause|resume|stop.
Read-only endpoints (/health, /status, /safety/*, /flexcell/status, /flexcell/log, /ws) stay open.
"""
import hmac
import logging
import os
from typing import Optional

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)


def configured_key() -> str:
    return os.environ.get("NEXUS_API_KEY", "").strip()


def auth_enabled() -> bool:
    return bool(configured_key())


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = configured_key()
    if not expected:
        return  # auth is off
    if not x_api_key or not hmac.compare_digest(x_api_key.strip().encode("utf-8"), expected.encode("utf-8")):
        logger.warning("Rejected a request with a missing or wrong API key")
        raise HTTPException(status_code=401, detail="Missing or invalid API key",
                            headers={"WWW-Authenticate": "ApiKey"})
