"""Integration tests for evobrain + FTS5 primary+fallback in memory_manager."""

import pytest
from unittest.mock import patch, MagicMock


class TestEngineSelection:
    def test_fts5_is_default(self):
        from backend.agent_runtime.evobrain_client import get_engine
        assert get_engine() == "fts5"

    def test_evobrain_when_env_set(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "evobrain")
        from backend.agent_runtime.evobrain_client import get_engine
        assert get_engine() == "evobrain"

    def test_invalid_env_falls_back_to_fts5(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "bogus")
        from backend.agent_runtime.evobrain_client import get_engine
        assert get_engine() == "fts5"


class TestGetMemoriesForContext:
    """Test get_memories_for_context with mocked database."""

    def test_fts5_returns_formatted_markdown(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "fts5")
        monkeypatch.delenv("EVONIC_MEMORY_ENGINE", raising=False)
        fake_memories = [
            {"id": 1, "content": "User prefers Python", "category": "preference"},
        ]
        with patch("backend.agent_runtime.memory_manager.db.search_memories",
                   return_value=fake_memories):
            from backend.agent_runtime.memory_manager import get_memories_for_context
            msgs = [{"role": "user", "content": "What language?"}]
            result = get_memories_for_context("test-agent", msgs)
            assert result is not None
            assert "User prefers Python" in result
            assert "## Memory" in result

    def test_fts5_no_memories_returns_none(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "fts5")
        with patch("backend.agent_runtime.memory_manager.db.search_memories", return_value=[]), \
             patch("backend.agent_runtime.memory_manager.db.get_recent_memories", return_value=[]):
            from backend.agent_runtime.memory_manager import get_memories_for_context
            msgs = [{"role": "user", "content": "query"}]
            result = get_memories_for_context("test-agent", msgs)
            assert result is None

    def test_fts5_no_user_message_uses_recent(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "fts5")
        fake_recent = [
            {"id": 2, "content": "User prefers Golang", "category": "preference"},
        ]
        with patch("backend.agent_runtime.memory_manager.db.search_memories", return_value=[]), \
             patch("backend.agent_runtime.memory_manager.db.get_recent_memories", return_value=fake_recent):
            from backend.agent_runtime.memory_manager import get_memories_for_context
            msgs = []  # No user message
            result = get_memories_for_context("test-agent", msgs)
            assert result is not None
            assert "User prefers Golang" in result

    def test_evobrain_primary_fallback_to_fts5(self, monkeypatch):
        """When evobrain is primary but fails, fall back to FTS5."""
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "evobrain")
        fake_fts5 = [
            {"id": 3, "content": "User prefers Rust", "category": "preference"},
        ]
        with patch(
            "backend.agent_runtime.memory_manager._try_evobrain_retrieval",
            return_value=None  # evobrain fails
        ), patch(
            "backend.agent_runtime.memory_manager.db.search_memories",
            return_value=fake_fts5
        ):
            from backend.agent_runtime.memory_manager import get_memories_for_context
            msgs = [{"role": "user", "content": "language preference"}]
            result = get_memories_for_context("test-agent", msgs)
            assert result is not None
            assert "User prefers Rust" in result


class TestStoreMemory:
    def test_stores_to_fts5_by_default(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "fts5")
        with patch("backend.agent_runtime.memory_manager.db.add_memory", return_value=42), \
             patch("backend.agent_runtime.memory_manager._extract_dimension", return_value="test.dim"), \
             patch("backend.agent_runtime.memory_manager._backfill_null_dimensions"), \
             patch("backend.agent_runtime.memory_manager.db.get_memories_by_dimension", return_value=[]), \
             patch("backend.agent_runtime.memory_manager._try_evobrain_store", return_value=False):
            from backend.agent_runtime.memory_manager import store_memory
            result = store_memory("test-agent", "sess-1", "Test fact", "preference")
            assert result["id"] == 42
            assert result["result"] == "Memory stored."

    def test_empty_content_returns_error(self):
        from backend.agent_runtime.memory_manager import store_memory
        result = store_memory("test-agent", "sess-1", "", "general")
        assert "error" in result

    def test_dual_write_attempted_when_evobrain_configured(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "evobrain")
        with patch("backend.agent_runtime.memory_manager.db.add_memory", return_value=42), \
             patch("backend.agent_runtime.memory_manager._extract_dimension", return_value="test.dim"), \
             patch("backend.agent_runtime.memory_manager._backfill_null_dimensions"), \
             patch("backend.agent_runtime.memory_manager.db.get_memories_by_dimension", return_value=[]), \
             patch("backend.agent_runtime.memory_manager._try_evobrain_store", return_value=True):
            from backend.agent_runtime.memory_manager import store_memory
            result = store_memory("test-agent", "sess-1", "Test fact", "preference")
            assert result["id"] == 42
            assert result.get("evobrain") == "stored"


class TestSearchMemories:
    def test_fts5_search_returns_results(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "fts5")
        fake = [{"id": 1, "content": "User prefers Python", "category": "preference",
                 "created_at": "2026-01-01"}]
        with patch("backend.agent_runtime.memory_manager.db.search_memories", return_value=fake):
            from backend.agent_runtime.memory_manager import search_memories
            result = search_memories("test-agent", "Python")
            assert result["count"] == 1
            assert result["memories"][0]["content"] == "User prefers Python"

    def test_fts5_search_no_match_returns_empty(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "fts5")
        with patch("backend.agent_runtime.memory_manager.db.search_memories", return_value=[]), \
             patch("backend.agent_runtime.memory_manager.db.get_recent_memories", return_value=[]):
            from backend.agent_runtime.memory_manager import search_memories
            result = search_memories("test-agent", "nonexistent")
            assert result["count"] == 0
            assert result["memories"] == []

    def test_evobrain_search_falls_back_to_fts5_when_unavailable(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "evobrain")
        fake_fts5 = [{"id": 1, "content": "User prefers Python", "category": "preference",
                      "created_at": "2026-01-01"}]
        with patch(
            "backend.agent_runtime.memory_manager.evobrain_search",
            return_value=None  # evobrain unavailable
        ), patch(
            "backend.agent_runtime.memory_manager.db.search_memories",
            return_value=fake_fts5
        ):
            from backend.agent_runtime.memory_manager import search_memories
            result = search_memories("test-agent", "Python")
            assert result["count"] == 1
            assert result["memories"][0]["content"] == "User prefers Python"


class TestEvobrainRetrievalFormatting:
    def test_skips_when_not_evobrain_engine(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "fts5")
        from backend.agent_runtime.memory_manager import _try_evobrain_retrieval
        result = _try_evobrain_retrieval("test-agent", "query")
        assert result is None

    def test_formats_evobrain_hits_into_markdown(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "evobrain")
        fake_hits = {
            "query": "preference",
            "hits": [
                {
                    "rank": 1,
                    "slug": "inbox/fact-1",
                    "title": "User prefers Javanese",
                    "snippet": "User prefers Javanese language",
                    "evidence": "exact_title_match",
                    "source_dir": "inbox",
                    "score": 0.05,
                }
            ]
        }
        with patch(
            "backend.agent_runtime.memory_manager.evobrain_search",
            return_value=fake_hits
        ):
            from backend.agent_runtime.memory_manager import _try_evobrain_retrieval
            result = _try_evobrain_retrieval("test-agent", "preference", limit=8)
            assert result is not None
            assert "## Memory (Evobrain)" in result
            assert "User prefers Javanese" in result
            assert "exact_title_match" in result

    def test_returns_none_when_evobrain_search_fails(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "evobrain")
        with patch(
            "backend.agent_runtime.memory_manager.evobrain_search",
            side_effect=Exception("connection refused")
        ):
            from backend.agent_runtime.memory_manager import _try_evobrain_retrieval
            result = _try_evobrain_retrieval("test-agent", "query")
            assert result is None

    def test_returns_none_when_no_hits(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "evobrain")
        with patch(
            "backend.agent_runtime.memory_manager.evobrain_search",
            return_value={"query": "test", "hits": [], "cached": False}
        ):
            from backend.agent_runtime.memory_manager import _try_evobrain_retrieval
            result = _try_evobrain_retrieval("test-agent", "query")
            assert result is None


class TestEvobrainStore:
    def test_skips_when_not_evobrain_engine(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "fts5")
        from backend.agent_runtime.memory_manager import _try_evobrain_store
        result = _try_evobrain_store("test-agent", "fact", "general")
        assert result is False

    def test_returns_false_when_capture_fails(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "evobrain")
        with patch(
            "backend.agent_runtime.memory_manager.capture",
            return_value=None
        ):
            from backend.agent_runtime.memory_manager import _try_evobrain_store
            result = _try_evobrain_store("test-agent", "fact", "general")
            assert result is False

    def test_returns_true_when_capture_succeeds(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "evobrain")
        with patch(
            "backend.agent_runtime.memory_manager.capture",
            return_value={"text": "fact", "category": "general"}
        ):
            from backend.agent_runtime.memory_manager import _try_evobrain_store
            result = _try_evobrain_store("test-agent", "fact", "general")
            assert result is True
