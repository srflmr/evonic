"""
evobrain_client.py -- CLI subprocess wrapper for Evobrain.

Provides a Python interface to the evobrain static binary via subprocess.
On any failure (timeout, non-zero exit, bad JSON, binary missing), returns
None so callers can transparently fall back to the FTS5 pipeline.
"""

import json
import os
import subprocess
import logging

logger = logging.getLogger(__name__)

_EVOBRAIN_BINARY = os.environ.get("EVOBRAIN_BINARY", "shared/bin/evobrain")
_EVOBRAIN_TIMEOUT = int(os.environ.get("EVOBRAIN_TIMEOUT", "5"))
_MEMORY_ENGINE = os.environ.get("EVONIC_MEMORY_ENGINE", "fts5")


def get_engine() -> str:
    """Return the configured primary memory engine ('evobrain' or 'fts5')."""
    engine = os.environ.get("EVONIC_MEMORY_ENGINE", "fts5")
    if engine not in ("evobrain", "fts5"):
        return "fts5"
    return engine


def is_available() -> bool:
    """Check whether the evobrain binary exists and is executable."""
    return os.path.isfile(_EVOBRAIN_BINARY) and os.access(_EVOBRAIN_BINARY, os.X_OK)


def _run(brain_dir: str, args: list, timeout: int = None) -> dict:
    """Run evobrain CLI and return parsed JSON, or None on any failure."""
    if timeout is None:
        timeout = _EVOBRAIN_TIMEOUT
    cmd = [_EVOBRAIN_BINARY, "--brain", brain_dir, "--json"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning("evobrain exited with code %d: %s", result.returncode, result.stderr.strip()[:200])
            return None
        if not result.stdout.strip():
            return None
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        logger.warning("evobrain subprocess timed out after %ds", timeout)
        return None
    except json.JSONDecodeError:
        logger.warning("evobrain returned invalid JSON")
        return None
    except FileNotFoundError:
        logger.warning("evobrain binary not found at %s", _EVOBRAIN_BINARY)
        return None
    except Exception as e:
        logger.warning("evobrain subprocess error: %s", e)
        return None


def _get_brain_dir(agent_id: str) -> str:
    """Return the evobrain directory path for a given agent."""
    return f"agents/{agent_id}/brain"


def init_brain(agent_id: str) -> bool:
    """Initialize a new evobrain directory for the agent. Returns True on success."""
    brain_dir = _get_brain_dir(agent_id)
    if not is_available():
        return False
    if os.path.isdir(brain_dir) and os.path.exists(os.path.join(brain_dir, ".evobrain.db")):
        return True
    os.makedirs(brain_dir, exist_ok=True)
    result = _run(brain_dir, ["init"])
    return result is not None


def capture(agent_id: str, text: str, category: str = "general") -> dict:
    """Capture a fact/thought into the agent's evobrain.

    Returns dict with {slug, path} or None on failure.
    """
    brain_dir = _get_brain_dir(agent_id)
    if not os.path.isdir(brain_dir) or not os.path.exists(os.path.join(brain_dir, ".evobrain.db")):
        if not init_brain(agent_id):
            return None
    # Build a safe title: strip YAML-breaking characters (brackets, quotes, colons)
    safe_title = (f"{category}: {text[:80]}"
                  .replace("[", "(").replace("]", ")")
                  .replace('"', "").replace("'", "")
                  .replace(":", " -"))
    result = _run(brain_dir, ["capture", "--title", safe_title, text])
    if not result:
        return None
    # capture output is plain text in JSON mode: "captured -> slug (path)"
    return {"text": text, "category": category, "raw": result}


def search(agent_id: str, query: str, limit: int = 8) -> dict:
    """Search the agent's evobrain with hybrid retrieval.

    Returns the full JSON response (with 'hits' array) or None on failure.
    """
    brain_dir = _get_brain_dir(agent_id)
    if not os.path.isdir(brain_dir) or not os.path.exists(os.path.join(brain_dir, ".evobrain.db")):
        return None
    return _run(brain_dir, ["search", "--limit", str(limit), query])


def think(agent_id: str, query: str) -> dict:
    """Brain-layer synthesis with gap analysis.

    Returns the full JSON response or None on failure.
    """
    brain_dir = _get_brain_dir(agent_id)
    if not os.path.isdir(brain_dir) or not os.path.exists(os.path.join(brain_dir, ".evobrain.db")):
        return None
    return _run(brain_dir, ["think", query])


def sync(agent_id: str) -> bool:
    """Re-sync markdown files into the database. Returns True on success."""
    brain_dir = _get_brain_dir(agent_id)
    if not os.path.isdir(brain_dir) or not os.path.exists(os.path.join(brain_dir, ".evobrain.db")):
        return False
    return _run(brain_dir, ["sync"]) is not None
