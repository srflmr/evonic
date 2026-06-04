"""Tests for memory conflict detection and superseding."""

import pytest

from models.chat import AgentChatDB


@pytest.fixture
def chat_db(tmp_path):
    """Create an isolated AgentChatDB for testing."""
    agent_dir = tmp_path / 'agents' / 'test-agent'
    agent_dir.mkdir(parents=True)
    return AgentChatDB(str(agent_dir))


class TestSchemaAndColumns:
    """Verify the new columns exist after migration."""

    def test_dimension_and_superseded_by_columns_exist(self, chat_db):
        import sqlite3
        with chat_db._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(memories)")
            columns = {row[1] for row in cursor.fetchall()}
        assert 'dimension' in columns
        assert 'superseded_by' in columns

    def test_dimension_index_exists(self, chat_db):
        import sqlite3
        with chat_db._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA index_list(memories)")
            indexes = {row[1] for row in cursor.fetchall()}
        assert 'idx_memories_dimension' in indexes


class TestAddMemoryWithDimension:
    """Test add_memory accepts and stores the dimension parameter."""

    def test_add_memory_with_dimension(self, chat_db):
        mid = chat_db.add_memory("User prefers Sundanese", "preference",
                                 dimension="user.language_preference")
        memories = chat_db.get_all_memories()
        assert len(memories) == 1
        assert memories[0]['dimension'] == 'user.language_preference'

    def test_add_memory_without_dimension(self, chat_db):
        mid = chat_db.add_memory("Some random fact", "general")
        memories = chat_db.get_all_memories()
        assert len(memories) == 1
        assert memories[0]['dimension'] is None

    def test_update_memory_with_dimension(self, chat_db):
        mid = chat_db.add_memory("Old content", "preference")
        chat_db.update_memory(mid, "New content", dimension="user.language_preference")
        memories = chat_db.get_all_memories()
        assert memories[0]['content'] == 'New content'
        assert memories[0]['dimension'] == 'user.language_preference'


class TestGetMemoriesByDimension:

    def test_returns_matching_dimension(self, chat_db):
        chat_db.add_memory("Prefers Javanese", "preference",
                           dimension="user.language_preference")
        chat_db.add_memory("Works at Acme", "user_info",
                           dimension="user.employer")
        result = chat_db.get_memories_by_dimension("user.language_preference")
        assert len(result) == 1
        assert result[0]['content'] == 'Prefers Javanese'

    def test_excludes_expired(self, chat_db):
        mid = chat_db.add_memory("Prefers Javanese", "preference",
                                 dimension="user.language_preference")
        chat_db.expire_memory(mid)
        result = chat_db.get_memories_by_dimension("user.language_preference")
        assert len(result) == 0

    def test_excludes_superseded(self, chat_db):
        mid1 = chat_db.add_memory("Prefers Javanese", "preference",
                                  dimension="user.language_preference")
        mid2 = chat_db.add_memory("Prefers Sundanese", "preference",
                                  dimension="user.language_preference")
        chat_db.supersede_memory(mid1, mid2)
        result = chat_db.get_memories_by_dimension("user.language_preference")
        assert len(result) == 1
        assert result[0]['content'] == 'Prefers Sundanese'


class TestSupersedeMemory:

    def test_marks_old_memory_as_superseded(self, chat_db):
        mid1 = chat_db.add_memory("Prefers Javanese", "preference",
                                  dimension="user.language_preference")
        mid2 = chat_db.add_memory("Prefers Sundanese", "preference",
                                  dimension="user.language_preference")
        chat_db.supersede_memory(mid1, mid2)

        all_mems = chat_db.get_all_memories()
        old = [m for m in all_mems if m['id'] == mid1][0]
        new = [m for m in all_mems if m['id'] == mid2][0]
        assert old['superseded_by'] == mid2
        assert new['superseded_by'] is None


class TestReadPathFiltering:
    """Verify search_memories and get_recent_memories exclude superseded entries."""

    def test_search_memories_excludes_superseded(self, chat_db):
        mid1 = chat_db.add_memory("User prefers Javanese language", "preference",
                                  dimension="user.language_preference")
        mid2 = chat_db.add_memory("User prefers Sundanese language", "preference",
                                  dimension="user.language_preference")
        chat_db.supersede_memory(mid1, mid2)

        results = chat_db.search_memories("language")
        assert len(results) == 1
        assert results[0]['id'] == mid2

    def test_get_recent_memories_excludes_superseded(self, chat_db):
        mid1 = chat_db.add_memory("Prefers Javanese", "preference",
                                  dimension="user.language_preference")
        mid2 = chat_db.add_memory("Prefers Sundanese", "preference",
                                  dimension="user.language_preference")
        chat_db.supersede_memory(mid1, mid2)

        results = chat_db.get_recent_memories()
        ids = [m['id'] for m in results]
        assert mid1 not in ids
        assert mid2 in ids

    def test_get_all_memories_still_includes_superseded(self, chat_db):
        """get_all_memories is for admin/audit — should NOT filter superseded."""
        mid1 = chat_db.add_memory("Prefers Javanese", "preference",
                                  dimension="user.language_preference")
        mid2 = chat_db.add_memory("Prefers Sundanese", "preference",
                                  dimension="user.language_preference")
        chat_db.supersede_memory(mid1, mid2)

        results = chat_db.get_all_memories()
        assert len(results) == 2


class TestNullDimensionBackwardCompat:
    """Memories without dimension should be unaffected by the new logic."""

    def test_null_dimension_memories_not_superseded(self, chat_db):
        mid1 = chat_db.add_memory("Some old fact", "general")
        mid2 = chat_db.add_memory("Another fact", "general")

        # Both have NULL dimension — neither should supersede the other
        results = chat_db.get_recent_memories()
        assert len(results) == 2

    def test_null_dimension_memories_visible_in_search(self, chat_db):
        chat_db.add_memory("User loves Python programming", "preference")
        results = chat_db.search_memories("Python")
        assert len(results) == 1


class TestConflictDetectionEndToEnd:
    """End-to-end test simulating the conflict detection flow at DB level.

    Uses isolated chat_db fixture to avoid cross-test contamination.
    """

    def test_supersedes_existing_on_same_dimension(self, chat_db):
        dim = 'user.language_preference'

        mid1 = chat_db.add_memory('User prefers Javanese', 'preference',
                                  dimension=dim)

        existing = chat_db.get_memories_by_dimension(dim)
        assert len(existing) == 1

        mid2 = chat_db.add_memory('User prefers Sundanese', 'preference',
                                  dimension=dim)
        for m in existing:
            chat_db.supersede_memory(m['id'], mid2)

        active = chat_db.get_memories_by_dimension(dim)
        assert len(active) == 1
        assert active[0]['content'] == 'User prefers Sundanese'

        all_mems = chat_db.get_all_memories()
        assert len(all_mems) == 2

    def test_no_supersede_when_dimension_is_none(self, chat_db):
        chat_db.add_memory('Vague fact 1', 'general')
        chat_db.add_memory('Vague fact 2', 'general')

        recent = chat_db.get_recent_memories()
        assert len(recent) == 2

    def test_triple_supersede_chain(self, chat_db):
        """Three conflicting values for same dimension — only the last survives."""
        dim = 'user.language_preference'

        mid1 = chat_db.add_memory('Prefers Javanese', 'preference', dimension=dim)

        existing = chat_db.get_memories_by_dimension(dim)
        mid2 = chat_db.add_memory('Prefers Sundanese', 'preference', dimension=dim)
        for m in existing:
            chat_db.supersede_memory(m['id'], mid2)

        existing = chat_db.get_memories_by_dimension(dim)
        mid3 = chat_db.add_memory('Prefers Indonesian', 'preference', dimension=dim)
        for m in existing:
            chat_db.supersede_memory(m['id'], mid3)

        active = chat_db.get_memories_by_dimension(dim)
        assert len(active) == 1
        assert active[0]['content'] == 'Prefers Indonesian'

        search_results = chat_db.search_memories('Prefers')
        ids = [m['id'] for m in search_results]
        assert mid3 in ids
        assert mid1 not in ids
        assert mid2 not in ids
