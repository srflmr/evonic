"""Tests for api_rate_limit.classify_request tier classification.

Regression guard for #627 / FINDING-004: cheap chat reads/polls must NOT consume
the small `chat` tier — only actual LLM-send POSTs do.
"""
import unittest

from models.api_rate_limit import classify_request


class TestClassifyRequest(unittest.TestCase):
    AID = "/api/agents/agent_x"

    def test_chat_send_post_is_chat_tier(self):
        self.assertEqual(classify_request(f"{self.AID}/chat", "POST"), "chat")

    def test_chat_approve_post_is_chat_tier(self):
        self.assertEqual(classify_request(f"{self.AID}/chat/approve", "POST"), "chat")

    def test_chat_get_messages_is_poll_tier(self):
        # GET /chat is the polling/messages read, not a send
        self.assertEqual(classify_request(f"{self.AID}/chat", "GET"), "poll")

    def test_chat_read_endpoints_are_poll_tier(self):
        for sub in ("history", "poll", "state", "session", "summary", "events",
                    "stream", "llm-preview"):
            self.assertEqual(
                classify_request(f"{self.AID}/chat/{sub}", "GET"), "poll",
                f"/chat/{sub} should be poll tier",
            )

    def test_chat_clear_post_is_poll_tier(self):
        # clear is a cheap mutation, not an LLM send
        self.assertEqual(classify_request(f"{self.AID}/chat/clear", "POST"), "poll")

    def test_upload_endpoints_unchanged(self):
        self.assertEqual(classify_request(f"{self.AID}/artifacts", "POST"), "upload")
        self.assertEqual(classify_request(f"{self.AID}/avatar", "POST"), "upload")
        self.assertEqual(classify_request("/api/plugins/install", "POST"), "upload")

    def test_crud_and_general_unchanged(self):
        self.assertEqual(classify_request("/api/agents", "GET"), "crud")
        self.assertEqual(classify_request(f"{self.AID}", "GET"), "crud")
        self.assertEqual(classify_request("/api/settings", "GET"), "general")

    def test_static_and_non_api_unchanged(self):
        self.assertEqual(classify_request("/static/js/app.js", "GET"), "static")
        self.assertIsNone(classify_request("/login", "POST"))


if __name__ == "__main__":
    unittest.main()
