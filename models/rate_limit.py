"""
SQLite-backed login rate limiter — persists across server restarts.

Replaces the in-memory Dict[str, List[float]] with a persistent store so that
failed-attempt counters survive process restarts, deploys, and SIGHUP reloads.

Schema
------
rate_limit(key TEXT PRIMARY KEY, count INTEGER NOT NULL, reset_at REAL NOT NULL)

  key      – IP address (or any identifier)
  count    – number of failed attempts within the current window
  reset_at – time.time() value when this window expires; when time.time()
             exceeds reset_at the row is treated as expired (count reset).

Thread safety
-------------
SQLite WAL mode + thread-local connections (same pattern as models/db.py).
No global locks needed — each thread gets its own connection.
"""

import sqlite3
import os
import threading
import time
from contextlib import contextmanager
from typing import Optional

import config

# ---------------------------------------------------------------------------
# Settings (mirrored from routes/auth.py — keep in sync)
# ---------------------------------------------------------------------------
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 15 * 60  # 15 minutes

# ---------------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------------
_RATE_LIMIT_DB = os.path.join(config.APP_ROOT, "shared", "db", "rate_limit.db")

# ---------------------------------------------------------------------------
# Connection management (thread-local, WAL mode)
# ---------------------------------------------------------------------------
_tls = threading.local()


@contextmanager
def _connect():
    """Yield a thread-local SQLite connection."""
    conn = getattr(_tls, "conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
        except Exception:
            conn = None

    if conn is None:
        os.makedirs(os.path.dirname(_RATE_LIMIT_DB), exist_ok=True)
        conn = sqlite3.connect(
            f"file:{_RATE_LIMIT_DB}?mode=rwc&busy_timeout=5000", uri=True
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        _init_table(conn)
        _tls.conn = conn

    with conn:
        yield conn


def close():
    """Close the thread-local connection (cleanup)."""
    conn = getattr(_tls, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _tls.conn = None


def _init_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS rate_limit (
            key      TEXT PRIMARY KEY,
            count    INTEGER NOT NULL DEFAULT 1,
            reset_at REAL    NOT NULL
        )"""
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_rate_limited(ip: str) -> bool:
    """Return True if *ip* has exceeded the failed-attempt limit."""
    now = time.time()
    with _connect() as conn:
        row = conn.execute(
            "SELECT count, reset_at FROM rate_limit WHERE key = ?", (ip,)
        ).fetchone()

    if row is None:
        return False

    count, reset_at = row
    if now >= reset_at:
        # Window expired — this row is stale; delete it lazily.
        _delete(ip)
        return False

    return count >= MAX_ATTEMPTS


def record_failed_attempt(ip: str) -> None:
    """Record one failed login attempt for *ip*.

    - If no row exists: insert with count=1, reset_at=now+WINDOW_SECONDS.
    - If row exists and window still active: increment count.
    - If row exists but window expired: reset count=1, update reset_at.
    """
    now = time.time()
    with _connect() as conn:
        row = conn.execute(
            "SELECT count, reset_at FROM rate_limit WHERE key = ?", (ip,)
        ).fetchone()

        if row is None:
            conn.execute(
                "INSERT INTO rate_limit (key, count, reset_at) VALUES (?, 1, ?)",
                (ip, now + WINDOW_SECONDS),
            )
        elif now >= row[1]:
            conn.execute(
                "UPDATE rate_limit SET count = 1, reset_at = ? WHERE key = ?",
                (now + WINDOW_SECONDS, ip),
            )
        else:
            conn.execute(
                "UPDATE rate_limit SET count = count + 1 WHERE key = ?", (ip,)
            )


def clear_attempts(ip: str) -> None:
    """Remove the rate-limit row for *ip* (called after successful login)."""
    _delete(ip)


def _delete(ip: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM rate_limit WHERE key = ?", (ip,))


def cleanup_expired() -> int:
    """Delete all rows where the window has expired.

    Returns the number of rows deleted (useful for logging).
    Intended for periodic calls (see *periodic_cleanup*).
    """
    now = time.time()
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM rate_limit WHERE reset_at <= ?", (now,))
        return cursor.rowcount


# ---------------------------------------------------------------------------
# Optional: periodic cleanup thread (daemon, runs every 5 minutes)
# ---------------------------------------------------------------------------

def _cleanup_loop(interval: float = 300.0) -> None:
    """Daemon thread entry point — calls *cleanup_expired* every *interval*
    seconds to prevent unbounded database growth."""
    while True:
        time.sleep(interval)
        try:
            deleted = cleanup_expired()
            if deleted:
                pass  # could log here if desired
        except Exception:
            pass  # silent — avoid crashing the daemon


def start_periodic_cleanup(interval: float = 300.0) -> threading.Thread:
    """Start a daemon thread that purges expired rate-limit rows.

    Called once at app startup (e.g. from create_app).
    """
    t = threading.Thread(target=_cleanup_loop, args=(interval,), daemon=True)
    t.start()
    return t
