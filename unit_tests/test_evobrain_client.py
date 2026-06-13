"""Tests for evobrain_client.py -- CLI subprocess wrapper."""

import subprocess
import pytest
from unittest.mock import patch, MagicMock

from backend.agent_runtime.evobrain_client import (
    get_engine, is_available, _run,
    init_brain, capture, search, think, sync, _get_brain_dir,
)


class TestGetEngine:
    def test_default_is_fts5(self, monkeypatch):
        monkeypatch.delenv("EVONIC_MEMORY_ENGINE", raising=False)
        assert get_engine() == "fts5"

    def test_evobrain_when_set(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "evobrain")
        assert get_engine() == "evobrain"

    def test_fts5_when_set(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "fts5")
        assert get_engine() == "fts5"

    def test_invalid_falls_back_to_fts5(self, monkeypatch):
        monkeypatch.setenv("EVONIC_MEMORY_ENGINE", "bogus")
        assert get_engine() == "fts5"


class TestIsAvailable:
    def test_returns_false_when_binary_missing(self, monkeypatch):
        monkeypatch.setattr(
            "backend.agent_runtime.evobrain_client._EVOBRAIN_BINARY",
            "/nonexistent/evobrain"
        )
        assert is_available() is False

    def test_returns_true_when_binary_exists(self, tmp_path):
        bin_path = tmp_path / "evobrain"
        bin_path.write_text("fake binary")
        bin_path.chmod(0o755)
        import backend.agent_runtime.evobrain_client as ec
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(ec, "_EVOBRAIN_BINARY", str(bin_path))
        try:
            assert ec.is_available() is True
        finally:
            monkeypatch.undo()


class TestBrainDir:
    def test_returns_agents_brain_path(self):
        path = _get_brain_dir("test-agent")
        assert path == "agents/test-agent/brain"


class TestRunSubprocess:
    def test_returns_parsed_json_on_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"ok": true}'
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            result = _run("/tmp/brain", ["search", "query"])
            assert result == {"ok": True}

    def test_returns_none_on_nonzero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error occurred"
        with patch("subprocess.run", return_value=mock_result):
            result = _run("/tmp/brain", ["search", "query"])
            assert result is None

    def test_returns_none_on_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            result = _run("/tmp/brain", ["search", "query"])
            assert result is None

    def test_returns_none_on_invalid_json(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json at all"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            result = _run("/tmp/brain", ["search", "query"])
            assert result is None

    def test_returns_none_on_file_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = _run("/tmp/brain", ["search", "query"])
            assert result is None


class TestInitBrain:
    def test_returns_false_when_unavailable(self):
        with patch("backend.agent_runtime.evobrain_client.is_available", return_value=False), \
             patch("os.makedirs"):
            result = init_brain("test-agent")
            assert result is False

    def test_returns_true_when_already_initialized(self, tmp_path):
        brain_dir = tmp_path / "brain"
        brain_dir.mkdir()
        (brain_dir / ".evobrain.db").write_text("fake db")
        with patch(
            "backend.agent_runtime.evobrain_client._get_brain_dir",
            return_value=str(brain_dir)
        ), patch("backend.agent_runtime.evobrain_client.is_available", return_value=True):
            result = init_brain("test-agent")
            assert result is True


class TestCapture:
    def test_returns_none_when_brain_not_initialized(self):
        with patch("backend.agent_runtime.evobrain_client.init_brain", return_value=False), \
             patch("os.path.isdir", return_value=False):
            result = capture("test-agent", "test fact")
            assert result is None


class TestSearch:
    def test_returns_none_when_brain_missing(self):
        with patch("os.path.isdir", return_value=False):
            result = search("test-agent", "query")
            assert result is None

    def test_returns_structured_result(self):
        with patch("os.path.isdir", return_value=True), \
             patch("os.path.exists", return_value=True), \
             patch(
                 "backend.agent_runtime.evobrain_client._run",
                 return_value={"query": "test", "hits": [], "cached": False}
             ):
            result = search("test-agent", "query")
            assert result is not None
            assert result["query"] == "test"
            assert result["hits"] == []


class TestThink:
    def test_returns_none_when_brain_missing(self):
        with patch("os.path.isdir", return_value=False):
            result = think("test-agent", "query")
            assert result is None


class TestSync:
    def test_returns_false_when_brain_missing(self):
        with patch("os.path.isdir", return_value=False):
            result = sync("test-agent")
            assert result is False
