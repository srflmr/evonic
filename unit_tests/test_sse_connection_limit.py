"""Tests for SSE connection limiting + stale-count reset (api_rate_limit).

Regression guard for the too_many_sse_connections storm: SSE counts are SQLite-
backed and leak across non-graceful restarts, eventually pegging a user at the
cap and 429-ing every new stream. reset_sse_connections() (called on startup)
clears the stale counts; the cap must also be high enough for the app's own
multi-stream + per-turn + reconnect-churn pattern.
"""
import os
import tempfile
import unittest


class TestSseConnectionLimit(unittest.TestCase):
    def setUp(self):
        import models.api_rate_limit as rl
        self.rl = rl
        rl._DB_PATH = os.path.join(tempfile.mkdtemp(), "rl.db")
        rl.close()

    def test_cap_is_generous(self):
        # 5 was too low for the app's own connection pattern (storm source).
        self.assertGreaterEqual(self.rl.SSE_MAX_CONCURRENT, 50)

    def test_allows_up_to_cap(self):
        last = None
        for _ in range(self.rl.SSE_MAX_CONCURRENT):
            last = self.rl.sse_register("user:admin")
        self.assertTrue(last[0])  # the cap-th connection is allowed

    def test_rejects_over_cap(self):
        for _ in range(self.rl.SSE_MAX_CONCURRENT):
            self.rl.sse_register("user:admin")
        allowed, _ = self.rl.sse_register("user:admin")
        self.assertFalse(allowed)

    def test_reset_clears_stale_peg(self):
        # Simulate a leaked/stale count pegged over the cap (as after a hard kill).
        for _ in range(self.rl.SSE_MAX_CONCURRENT + 20):
            self.rl.sse_register("user:admin")
        self.assertFalse(self.rl.sse_register("user:admin")[0])  # pegged → 429
        self.rl.reset_sse_connections()
        allowed, count = self.rl.sse_register("user:admin")
        self.assertTrue(allowed)
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
