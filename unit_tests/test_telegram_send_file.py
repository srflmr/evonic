"""Tests for Telegram outbound file sending (_do_send_file)."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch


def _make_channel():
    from backend.channels import telegram as tg_mod
    channel = tg_mod.TelegramChannel.__new__(tg_mod.TelegramChannel)
    channel._app = MagicMock()
    channel._app.bot.send_document = AsyncMock()
    channel._loop = None
    channel.channel_id = "ch_test"

    def _fake_run_async(coro):
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    channel._run_async = _fake_run_async
    return channel


def _patchers():
    """Mock the 'telegram' module so that 'from telegram import InputFile' works."""
    fake_inputfile = MagicMock()
    fake_inputfile.side_effect = lambda fh, filename=None: MagicMock(
        _file=fh, filename=filename)

    fake_telegram = MagicMock()
    fake_telegram.InputFile = fake_inputfile

    return (
        patch.dict("sys.modules", {
            "telegram": fake_telegram,
            "telegram.request": MagicMock(),
        }),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_send_file_missing_file_returns_false():
    with _patchers()[0]:
        channel = _make_channel()
        assert channel._do_send_file("123", "/nonexistent/file.pdf") is False


def test_send_file_oversized_returns_false():
    """Write a file just over 50 MB — should be rejected."""
    with _patchers()[0]:
        channel = _make_channel()
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"\x00" * (50 * 1024 * 1024 + 1))
            tmp = f.name
        try:
            assert channel._do_send_file("123", tmp) is False
        finally:
            os.unlink(tmp)


def test_send_file_success():
    with _patchers()[0]:
        channel = _make_channel()
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("hello world")
            tmp = f.name
        try:
            result = channel._do_send_file("123", tmp, caption="Here you go")
            assert result is True
            channel._app.bot.send_document.assert_called_once()
            kw = channel._app.bot.send_document.call_args.kwargs
            assert kw["chat_id"] == "123"
            assert kw["caption"] == "Here you go"
        finally:
            os.unlink(tmp)


def test_send_file_strips_markdown_from_caption():
    with _patchers()[0]:
        channel = _make_channel()
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("test")
            tmp = f.name
        try:
            channel._do_send_file("123", tmp, caption="**bold** and *italic*")
            kw = channel._app.bot.send_document.call_args.kwargs
            assert kw["caption"] == "bold and italic"
        finally:
            os.unlink(tmp)


def test_send_file_no_caption():
    with _patchers()[0]:
        channel = _make_channel()
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("test")
            tmp = f.name
        try:
            channel._do_send_file("123", tmp)
            kw = channel._app.bot.send_document.call_args.kwargs
            assert kw["caption"] is None
        finally:
            os.unlink(tmp)
