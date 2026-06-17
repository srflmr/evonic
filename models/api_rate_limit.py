"""
SQLite-backed tiered API rate limiter.

Replaces the missing per-endpoint rate limiting (FINDING-004) with a persistent
SQLite store that survives restarts. Tracks requests per-user (authenticated)
or per-IP (anonymous).

Tiers
-----
- chat:    10 req/min  — /api/agents/<id>/chat/*
- upload:   5 req/min  — POST /api/agents/<id>/artifacts, /avatar, /kb; /api/plugins
- crud:    30 req/min  — /api/agents* (excluding chat/upload sub-paths)
- general: 60 req/min  — all other /api/* endpoints
- static: 300 req/min  — /static/* (or unlimited, configurable)
- sse:     max 5 concurrent connections per user/IP

Schema
------
api_rate_limit(key TEXT PRIMARY KEY, tier TEXT NOT NULL, count INTEGER NOT NULL,
               window_start REAL NOT NULL, reset_at REAL NOT NULL)

  key          — "user:<id>" or "ip:<addr>"
  tier         — one of: chat, upload, crud, general, static
  count        — requests within the current window
  window_start — time.time() when the current window began
  reset_at     — time.time() when the window expires

sse_connections(key TEXT PRIMARY KEY, count INTEGER NOT NULL)

  key   — "user:<id>" or "ip:<addr>"
  count — current concurrent SSE connections
"""

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Optional, Tuple

import config

# ---------------------------------------------------------------------------
# Tier configuration: (requests_per_window, window_seconds)
# ---------------------------------------------------------------------------
TIERS = {
    "chat":    (10,  60),   # 10 req/min
    "upload":  (5,   60),   #  5 req/min
    "crud":    (30,  60),   # 30 req/min
    "general": (60,  60),   # 60 req/min
    "static":  (300, 60),   # 300 req/min (effectively unlimited for normal use)
}

SSE_MAX_CONCURRENT = 5  # max concurrent SSE connections per user/IP

# ---------------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------------
_DB_PATH = os.path.join(config.APP_ROOT, "shared", "db", "api_rate_limit.db")

# ---------------------------------------------------------------------------
# Thread-local connection management (WAL mode)
# ---------------------------------------------------------------------------
_tls = threading.local()


@contextmanager
def _connect():
    conn = getattr(_tls, "conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
        except Exception:
            conn = None

    if conn is None:
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
        conn = sqlite3.connect(
            f"file:{_DB_PATH}?mode=rwc&busy_timeout=5000", uri=True
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        _init_tables(conn)
        _tls.conn = conn

    with conn:
        yield conn


def close():
    conn = getattr(_tls, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _tls.conn = None


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_rate_limit (
            key         TEXT NOT NULL,
            tier        TEXT NOT NULL,
            count       INTEGER NOT NULL DEFAULT 0,
            window_start REAL NOT NULL,
            reset_at    REAL NOT NULL,
            PRIMARY KEY (key, tier)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sse_connections (
            key   TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0
        )
    """)


# ---------------------------------------------------------------------------
# Key construction
# ---------------------------------------------------------------------------

def _make_key(identifier: str) -> str:
    """Build a rate-limit key from user ID or IP."""
    return identifier  # already formatted as "user:<id>" or "ip:<addr>"


# ---------------------------------------------------------------------------
# Route → tier classification
# ---------------------------------------------------------------------------

def classify_request(path: str, method: str = "GET") -> str:
    """Return the rate-limit tier for a given request path and method.

    Classification rules (first match wins):
      1. /static/*                     → static
      2. /api/agents/<id>/chat/*       → chat
      3. POST /api/agents/<id>/artifacts* → upload
      4. POST /api/agents/<id>/avatar    → upload
      5. POST /api/agents/<id>/kb        → upload
      6. /api/plugins*                   → upload
      7. /api/agents*                    → crud
      8. /api/*                          → general
      9. everything else                 → None (no limit)
    """
    # Static assets
    if path.startswith("/static/"):
        return "static"

    # LLM Chat endpoints
    if "/api/agents/" in path and "/chat" in path:
        return "chat"

    # File/Plugin Upload endpoints (POST only)
    if method == "POST":
        if "/api/agents/" in path and (
            "/artifacts" in path or "/avatar" in path
        ):
            # Only POST to artifacts or avatar is an upload
            if path.rstrip("/").endswith("/artifacts") or path.rstrip("/").endswith("/avatar"):
                return "upload"
        if "/api/agents/" in path and "/kb" in path:
            if path.rstrip("/").endswith("/kb"):
                return "upload"
        if path.startswith("/api/plugins"):
            return "upload"

    # Agent CRUD
    if path.startswith("/api/agents"):
        return "crud"

    # All other API endpoints
    if path.startswith("/api/"):
        return "general"

    # Non-API routes (login, dashboard pages, etc.) — no rate limit
    return None


# ---------------------------------------------------------------------------
# SSE connection tracking
# ---------------------------------------------------------------------------

def sse_register(identifier: str) -> Tuple[bool, int]:
    """Register a new SSE connection. Returns (allowed, current_count)."""
    key = _make_key(identifier)
    now = time.time()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO sse_connections (key, count)
               VALUES (?, 1)
               ON CONFLICT(key) DO UPDATE SET count = count + 1""",
            (key,),
        )
        row = conn.execute(
            "SELECT count FROM sse_connections WHERE key = ?", (key,)
        ).fetchone()
        current = row[0] if row else 0
        allowed = current <= SSE_MAX_CONCURRENT
        if not allowed:
            # Roll back — don't count rejected connections
            conn.execute(
                "UPDATE sse_connections SET count = count - 1 WHERE key = ?",
                (key,),
            )
    return allowed, current


def sse_unregister(identifier: str) -> None:
    """Unregister an SSE connection when it closes."""
    key = _make_key(identifier)
    with _connect() as conn:
        conn.execute(
            """UPDATE sse_connections SET count = MAX(0, count - 1)
               WHERE key = ?""",
            (key,),
        )
        # Clean up zero-count rows
        conn.execute(
            "DELETE FROM sse_connections WHERE key = ? AND count <= 0", (key,)
        )


# ---------------------------------------------------------------------------
# Core rate-limit check
# ---------------------------------------------------------------------------

def check_rate_limit(identifier: str, tier: str) -> Tuple[bool, int, int, int]:
    """Check if a request is allowed under the given tier.

    Args:
        identifier: "user:<id>" or "ip:<addr>"
        tier: one of the TIERS keys

    Returns:
        (allowed, remaining, limit, retry_after_seconds)
    """
    if tier not in TIERS:
        return True, -1, -1, 0

    limit, window = TIERS[tier]
    key = _make_key(identifier)
    now = time.time()

    with _connect() as conn:
        row = conn.execute(
            """SELECT count, window_start, reset_at
               FROM api_rate_limit WHERE key = ? AND tier = ?""",
            (key, tier),
        ).fetchone()

        if row is None:
            # First request in window
            window_start = now
            reset_at = now + window
            conn.execute(
                """INSERT INTO api_rate_limit (key, tier, count, window_start, reset_at)
                   VALUES (?, ?, 1, ?, ?)""",
                (key, tier, window_start, reset_at),
            )
            return True, limit - 1, limit, 0

        count, window_start, reset_at = row
        if now >= reset_at:
            # Window expired — reset
            window_start = now
            reset_at = now + window
            conn.execute(
                """UPDATE api_rate_limit
                   SET count = 1, window_start = ?, reset_at = ?
                   WHERE key = ? AND tier = ?""",
                (window_start, reset_at, key, tier),
            )
            return True, limit - 1, limit, 0

        if count >= limit:
            # Rate limited
            retry_after = int(reset_at - now) + 1
            return False, 0, limit, retry_after

        # Within limit — increment
        new_count = count + 1
        conn.execute(
            "UPDATE api_rate_limit SET count = ? WHERE key = ? AND tier = ?",
            (new_count, key, tier),
        )
        remaining = limit - new_count
        return True, remaining, limit, 0


# ---------------------------------------------------------------------------
# Periodic cleanup
# ---------------------------------------------------------------------------

def cleanup_expired() -> int:
    """Delete expired rate-limit rows. Returns number of rows deleted."""
    now = time.time()
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM api_rate_limit WHERE reset_at <= ?", (now,)
        )
        return cursor.rowcount


def _cleanup_loop(interval: float = 300.0) -> None:
    while True:
        time.sleep(interval)
        try:
            cleanup_expired()
        except Exception:
            pass


def start_periodic_cleanup(interval: float = 300.0) -> threading.Thread:
    t = threading.Thread(target=_cleanup_loop, args=(interval,), daemon=True)
    t.start()
    return t
