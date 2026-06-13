"""
evomem_client.py -- CLI subprocess wrapper for Evomem.

Provides a Python interface to the evomem static binary via subprocess.
On any failure (timeout, non-zero exit, bad JSON, binary missing), returns
None so callers can transparently fall back to the FTS5 pipeline.
"""

import json
import os
import time
import subprocess
import logging

logger = logging.getLogger(__name__)

_EVOMEM_BINARY = os.environ.get("EVOMEM_BINARY", "shared/bin/evomem")
_EVOMEM_TIMEOUT = int(os.environ.get("EVOMEM_TIMEOUT", "5"))

# Operational tracing for evomem internals, shared by all evomem modules.
# Set EVOMEM_VERBOSE=1 to emit these traces at INFO level (so they appear in
# normal logs); otherwise they go to DEBUG.
vlogger = logging.getLogger("evomem")
_EVOMEM_VERBOSE = os.environ.get("EVOMEM_VERBOSE", "").strip().lower() in (
    "1", "true", "yes", "on")
if _EVOMEM_VERBOSE and vlogger.level == logging.NOTSET:
    vlogger.setLevel(logging.DEBUG)


def vlog(msg, *args):
    """Emit an evomem operational trace (INFO when EVOMEM_VERBOSE, else DEBUG)."""
    vlogger.log(logging.INFO if _EVOMEM_VERBOSE else logging.DEBUG, msg, *args)


def _summarize(parsed) -> str:
    """Compact one-line description of a parsed evomem JSON result."""
    if not isinstance(parsed, dict):
        return type(parsed).__name__
    for key in ("hits", "facts", "edges"):
        if isinstance(parsed.get(key), list):
            return f"{len(parsed[key])} {key}"
    if "links" in parsed:  # stats
        return f"pages={parsed.get('pages')} links={parsed.get('links')} " \
               f"dangling={parsed.get('dangling_links')}"
    if "links_resolved" in parsed:  # sync
        return f"sync added={parsed.get('added')} updated={parsed.get('updated')} " \
               f"links_resolved={parsed.get('links_resolved')}"
    return "ok"


def get_engine() -> str:
    """Return the active primary memory engine ('evomem' or 'fts5').

    Evomem is the default. It transparently downgrades to FTS5 when the
    binary is missing/not executable, so binary-less deployments keep working.
    EVONIC_MEMORY_ENGINE overrides the default; an unknown value is treated as
    'evomem'.  Backward compatibility: 'evobrain' is accepted as a synonym.
    """
    engine = os.environ.get("EVONIC_MEMORY_ENGINE", "evomem").strip().lower()
    # Backward compatibility: accept "evobrain" as a synonym for "evomem"
    if engine == "evobrain":
        engine = "evomem"
    if engine not in ("evomem", "fts5"):
        engine = "evomem"
    if engine == "evomem" and not is_available():
        return "fts5"
    return engine


def is_available() -> bool:
    """Check whether the evomem binary exists and is executable."""
    return os.path.isfile(_EVOMEM_BINARY) and os.access(_EVOMEM_BINARY, os.X_OK)


def _run(brain_dir: str, args: list, timeout: int = None,
         expect_json: bool = True) -> dict:
    """Run evomem CLI and return parsed JSON, or None on any failure.

    Some commands (e.g. `init`) print a plain-text confirmation even with
    --json; pass expect_json=False for those to return the raw stdout string
    without logging a spurious JSON warning.
    """
    if timeout is None:
        timeout = _EVOMEM_TIMEOUT
    cmd = [_EVOMEM_BINARY, "--brain", brain_dir, "--json"] + args
    cmd_desc = " ".join(str(a) for a in args)
    vlog("run: %s (brain=%s)", cmd_desc, brain_dir)
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        dt_ms = (time.time() - t0) * 1000
        if result.returncode != 0:
            logger.warning("evomem exited with code %d: %s", result.returncode, result.stderr.strip()[:200])
            return None
        if not result.stdout.strip():
            vlog("run: %s -> empty (%.0fms)", cmd_desc, dt_ms)
            return None
        if not expect_json:
            vlog("run: %s -> text ok (%.0fms)", cmd_desc, dt_ms)
            return result.stdout.strip()
        parsed = json.loads(result.stdout)
        vlog("run: %s -> %s (%.0fms)", cmd_desc, _summarize(parsed), dt_ms)
        return parsed
    except subprocess.TimeoutExpired:
        logger.warning("evomem subprocess timed out after %ds", timeout)
        return None
    except json.JSONDecodeError:
        logger.warning("evomem returned invalid JSON")
        return None
    except FileNotFoundError:
        logger.warning("evomem binary not found at %s", _EVOMEM_BINARY)
        return None
    except Exception as e:
        logger.warning("evomem subprocess error: %s", e)
        return None


def _get_brain_dir(agent_id: str) -> str:
    """Return the evomem directory path for a given agent."""
    return f"agents/{agent_id}/brain"


def init_brain(agent_id: str) -> bool:
    """Initialize a new evomem directory for the agent. Returns True on success."""
    brain_dir = _get_brain_dir(agent_id)
    if not is_available():
        return False
    db_path = os.path.join(brain_dir, ".evomem.db")
    if os.path.isdir(brain_dir) and os.path.exists(db_path):
        return True
    os.makedirs(brain_dir, exist_ok=True)
    # `init` prints a plain-text confirmation even with --json, so verify success
    # by the presence of the database file rather than a parsed JSON result.
    _run(brain_dir, ["init"], expect_json=False)
    return os.path.exists(db_path)


def capture(agent_id: str, text: str, category: str = "general") -> dict:
    """Capture a fact/thought into the agent's evomem.

    Returns dict with {slug, path} or None on failure.
    """
    brain_dir = _get_brain_dir(agent_id)
    if not os.path.isdir(brain_dir) or not os.path.exists(os.path.join(brain_dir, ".evomem.db")):
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


def search(agent_id: str, query: str, limit: int = 8,
           mode: str = "balanced", timeout: int = None) -> dict:
    """Search the agent's evomem with hybrid retrieval.

    mode is one of 'conservative' | 'balanced' | 'tokenmax'.
    Returns the full JSON response (with 'hits' array) or None on failure.
    """
    brain_dir = _get_brain_dir(agent_id)
    if not os.path.isdir(brain_dir) or not os.path.exists(os.path.join(brain_dir, ".evomem.db")):
        return None
    return _run(brain_dir, ["search", "--mode", mode, "--limit", str(limit), query],
                timeout=timeout)


def think(agent_id: str, query: str, mode: str = "balanced",
          timeout: int = None) -> dict:
    """Brain-layer synthesis with gap analysis.

    Returns the full JSON response ({facts, gaps, ...}) or None on failure.
    """
    brain_dir = _get_brain_dir(agent_id)
    if not os.path.isdir(brain_dir) or not os.path.exists(os.path.join(brain_dir, ".evomem.db")):
        return None
    return _run(brain_dir, ["think", "--mode", mode, query], timeout=timeout)


def graph_query(agent_id: str, start: str, edge: str = None,
                hops: int = 2, timeout: int = None) -> dict:
    """Traverse typed edges from a start page (slug, title, or alias).

    Returns {start, edges:[{src_slug, dst_slug, edge_type, hop}], cached} or
    None on failure. `edge` optionally filters by edge type.
    """
    brain_dir = _get_brain_dir(agent_id)
    if not os.path.isdir(brain_dir) or not os.path.exists(os.path.join(brain_dir, ".evomem.db")):
        return None
    args = ["graph-query", "--hops", str(hops), start]
    if edge:
        args[1:1] = ["--edge", edge]  # insert before positional start
    return _run(brain_dir, args, timeout=timeout)


def sync(agent_id: str) -> bool:
    """Re-sync markdown files into the database. Returns True on success."""
    brain_dir = _get_brain_dir(agent_id)
    if not os.path.isdir(brain_dir) or not os.path.exists(os.path.join(brain_dir, ".evomem.db")):
        return False
    return _run(brain_dir, ["sync"]) is not None
