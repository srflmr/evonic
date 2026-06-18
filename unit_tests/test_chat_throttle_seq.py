"""Tests for ChatThrottle seq preservation (live-SSE phantom gap-fill fix).

Merged 'thinking' batches must carry the highest batched chunk's seq so the
browser's gap detector advances _lastSeq over the folded chunks instead of
firing a spurious gap-fill (and re-rendering duplicate CoT).
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.realtime import ChatThrottle


class TestChatThrottleSeq(unittest.TestCase):

    def _t(self):
        # 0ms throttle so every batched chunk flushes immediately and we can
        # drive the batching deterministically without sleeping.
        return ChatThrottle(throttle_ms=0)

    def test_first_thinking_passes_through_with_seq(self):
        t = self._t()
        out = t.feed('thinking', {'content': 'a', 'seq': 1})
        self.assertEqual(out, [('thinking', {'content': 'a', 'seq': 1})])

    def test_merged_batch_carries_highest_seq(self):
        t = ChatThrottle(throttle_ms=10_000)  # never time-flush; flush via non-thinking
        t.feed('thinking', {'content': 'a', 'seq': 1})   # first — passes through
        self.assertEqual(t.feed('thinking', {'content': 'b', 'seq': 2}), [])  # batched
        self.assertEqual(t.feed('thinking', {'content': 'c', 'seq': 3}), [])  # batched
        # A non-thinking event flushes the batch first, then itself.
        out = t.feed('tool_call_started', {'tool': 'x', 'seq': 4})
        self.assertEqual(out, [
            ('thinking', {'content': 'bc', 'seq': 3}),       # merged carries seq=3
            ('tool_call_started', {'tool': 'x', 'seq': 4}),  # contiguous next
        ])

    def test_flush_carries_seq(self):
        t = ChatThrottle(throttle_ms=10_000)
        t.feed('thinking', {'content': 'a', 'seq': 5})  # first — passes through
        t.feed('thinking', {'content': 'b', 'seq': 6})  # batched
        t.feed('thinking', {'content': 'c', 'seq': 7})  # batched
        self.assertEqual(t.flush(), [('thinking', {'content': 'bc', 'seq': 7})])

    def test_empty_batch_flush_is_noop(self):
        t = ChatThrottle(throttle_ms=10_000)
        self.assertEqual(t.flush(), [])

    def test_no_seq_omitted_gracefully(self):
        # If chunks lack seq (shouldn't happen post-fix), merged event omits seq
        # rather than emitting seq=None.
        t = ChatThrottle(throttle_ms=10_000)
        t.feed('thinking', {'content': 'a'})  # first — passes through
        t.feed('thinking', {'content': 'b'})  # batched, no seq
        out = t.flush()
        self.assertEqual(out, [('thinking', {'content': 'b'})])
        self.assertNotIn('seq', out[0][1])


if __name__ == '__main__':
    unittest.main()
