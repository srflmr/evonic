import sqlite3
import os
import threading
from contextlib import contextmanager
from typing import Generator
import config
from models.schema import SchemaMixin, _migrate_db_to_subdir
from models.mixins import (
    EvaluationMixin,
    TestingMixin,
    ToolsMixin,
    AgentMixin,
    ChannelMixin,
    ChatDelegationMixin,
    SettingsMixin,
    ScheduleMixin,
    DashboardMixin,
    ModelsMixin,
    WorkplaceMixin,
    PortalMixin,
    SafetyRuleMixin,
    AttachmentsMixin,
    UserMixin,
    TransferJobMixin,
)


class Database(
    UserMixin,
    SchemaMixin,
    EvaluationMixin,
    TestingMixin,
    ToolsMixin,
    AgentMixin,
    ChannelMixin,
    ChatDelegationMixin,
    SettingsMixin,
    ScheduleMixin,
    DashboardMixin,
    ModelsMixin,
    WorkplaceMixin,
    PortalMixin,
    SafetyRuleMixin,
    AttachmentsMixin,
    TransferJobMixin,
):
    def __init__(self, db_path: str = config.DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _migrate_db_to_subdir(db_path)
        self._tls_db = threading.local()
        self._init_tables()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that returns a thread-local SQLite connection.
        The connection persists for the thread's lifetime — it is NOT closed on exit.
        PRAGMAs are set only once, on connection creation. Stale connections (from
        dead threads) are detected with SELECT 1 and recreated.
        Includes automatic transaction management (commit/rollback).
        """
        conn = getattr(self._tls_db, 'conn', None)
        if conn is not None:
            try:
                conn.execute("SELECT 1")
            except Exception:
                conn = None

        if conn is None:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=rwc&busy_timeout=10000", uri=True)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA wal_autocheckpoint=100")
            conn.execute("PRAGMA cache_size=-8000")
            conn.execute("PRAGMA mmap_size=268435456")
            self._tls_db.conn = conn

        with conn:
            yield conn

    def close(self):
        """Explicitly close the thread-local connection if it exists."""
        conn = getattr(self._tls_db, 'conn', None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._tls_db.conn = None


# Re-export chat classes for backward compatibility
from models.chat import AgentChatDB, AgentChatManager, agent_chat_manager  # noqa: F401

# Global singleton
db = Database()
