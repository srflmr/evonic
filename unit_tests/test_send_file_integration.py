"""Integration tests for the full send-file pipeline: PluginSDK -> AgentRuntime -> Channel."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch


def _make_channel_instance(channel_id, agent_id, app):
    from backend.channels import telegram as tg_mod
    ch = tg_mod.TelegramChannel.__new__(tg_mod.TelegramChannel)
    ch.channel_id = channel_id
    ch.agent_id = agent_id
    ch.config = {}
    ch._app = app
    ch._loop = None
    ch._running = True
    ch._outbound_buffer_seconds = 1.5
    from threading import Lock
    ch._buf = {}
    ch._buf_timers = {}
    ch._buf_lock = Lock()
    ch._last_sent = {}

    def _fake_run_async(coro):
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    ch._run_async = _fake_run_async
    return ch


def test_full_pipeline_plugin_sdk_to_channel():
    agent_id = "test_sf_agent"
    channel_id = "ch_integration_test"
    external_user_id = "user_98765"

    # 1. Mock telegram module
    fake_inputfile = MagicMock()
    fake_inputfile.side_effect = lambda fh, filename=None: MagicMock(
        _file=fh, filename=filename,
    )
    fake_telegram = MagicMock()
    fake_telegram.InputFile = fake_inputfile

    # 2. Fake PTB app
    app = MagicMock()
    app.bot.send_document = AsyncMock()

    with patch.dict("sys.modules", {
        "telegram": fake_telegram,
        "telegram.request": MagicMock(),
    }):
        from models.db import db
        from backend.channels.registry import channel_manager
        from backend.plugin_sdk import PluginSDK

        # agent_runtime is likely a MagicMock stub from test_llm_loop_recovery.
        # Use side_effect to simulate send_file_as_bot without importing the
        # real AgentRuntime module (too heavy for the sandbox).
        def _fake_send_file_as_bot(session_id, file_path, caption=None,
                                    mime_type=None):
            session = db.get_session_with_details(session_id)
            if not session:
                return False
            channel_id = session.get('channel_id')
            if channel_id:
                instance = channel_manager._active.get(channel_id)
                if instance and instance.is_running:
                    instance.send_file(session['external_user_id'],
                                       file_path, caption, mime_type)
            return True

        from unittest.mock import patch as _patch
        with _patch('backend.agent_runtime.agent_runtime.send_file_as_bot',
                     side_effect=_fake_send_file_as_bot):
            # 3. Create agent and register channel
            db.create_agent({"id": agent_id, "name": agent_id, "system_prompt": ""})

            ch = _make_channel_instance(channel_id, agent_id, app)
            channel_manager._active[channel_id] = ch

            try:
                with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
                    f.write("integration test content")
                    tmp = f.name
                try:
                    sdk = PluginSDK("test_plugin", {}, {})
                    result = sdk.send_file(
                        agent_id, external_user_id, channel_id,
                        file_path=tmp, caption="Integration caption",
                    )
                    assert result["success"] is True
                    assert "session_id" in result

                    app.bot.send_document.assert_called_once()
                    kw = app.bot.send_document.call_args.kwargs
                    assert kw["chat_id"] == external_user_id
                    assert kw["caption"] == "Integration caption"
                finally:
                    os.unlink(tmp)
            finally:
                channel_manager._active.pop(channel_id, None)
                with db._connect() as conn:
                    conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
