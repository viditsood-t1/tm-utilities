"""
tests/test_sql_backend.py
--------------------------
Full test coverage for SQLHistoryBackend using SQLite in-memory.
"""

import pytest
from datetime import datetime, timedelta

from consolidated_utility.history.sql_backend import SQLHistoryBackend
from consolidated_utility.utils.models import HistoryEntry, Message, MessageRole


# ─────────────────────────────────────────────────────────────────────────────
# save_session / get_session
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveAndGet:
    def test_save_new_session(self, sql_backend, sample_entry):
        saved = sql_backend.save_session(sample_entry)
        assert saved.session_id == sample_entry.session_id

    def test_get_saved_session(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        fetched = sql_backend.get_session(sample_entry.session_id)
        assert fetched is not None
        assert fetched.session_id == sample_entry.session_id
        assert fetched.user_id == sample_entry.user_id

    def test_get_nonexistent_session_returns_none(self, sql_backend):
        result = sql_backend.get_session("does-not-exist")
        assert result is None

    def test_messages_round_trip(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        fetched = sql_backend.get_session(sample_entry.session_id)
        assert len(fetched.messages) == 3
        assert fetched.messages[0].content == "Hello, how are you?"
        assert fetched.messages[0].role == MessageRole.USER

    def test_tags_and_metadata_persisted(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        fetched = sql_backend.get_session(sample_entry.session_id)
        assert "python" in fetched.tags
        assert fetched.metadata["source"] == "web"

    def test_overwrite_existing_session(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        # Modify and re-save
        sample_entry.messages = [Message(role=MessageRole.USER, content="new message")]
        sql_backend.save_session(sample_entry)
        fetched = sql_backend.get_session(sample_entry.session_id)
        assert len(fetched.messages) == 1
        assert fetched.messages[0].content == "new message"


# ─────────────────────────────────────────────────────────────────────────────
# append_messages
# ─────────────────────────────────────────────────────────────────────────────

class TestAppendMessages:
    def test_append_single_message(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        new_msg = Message(role=MessageRole.ASSISTANT, content="Follow-up answer")
        stub = HistoryEntry(user_id=sample_entry.user_id, messages=[new_msg])
        updated = sql_backend.append_messages(sample_entry.session_id, stub)
        assert len(updated.messages) == 4  # 3 original + 1 appended

    def test_append_multiple_messages(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        new_msgs = [
            Message(role=MessageRole.USER,      content="Q2"),
            Message(role=MessageRole.ASSISTANT, content="A2"),
        ]
        stub = HistoryEntry(user_id=sample_entry.user_id, messages=new_msgs)
        updated = sql_backend.append_messages(sample_entry.session_id, stub)
        assert len(updated.messages) == 5


# ─────────────────────────────────────────────────────────────────────────────
# get_sessions_by_user
# ─────────────────────────────────────────────────────────────────────────────

class TestGetSessionsByUser:
    def test_returns_correct_user_sessions(
        self, sql_backend, multi_entry_factory
    ):
        entries = multi_entry_factory("user-A", 5)
        other   = multi_entry_factory("user-B", 3)
        for e in entries + other:
            sql_backend.save_session(e)

        result = sql_backend.get_sessions_by_user("user-A")
        assert len(result) == 5
        assert all(e.user_id == "user-A" for e in result)

    def test_pagination_limit(self, sql_backend, multi_entry_factory):
        for e in multi_entry_factory("user-P", 10):
            sql_backend.save_session(e)
        page1 = sql_backend.get_sessions_by_user("user-P", limit=4)
        assert len(page1) == 4

    def test_pagination_offset(self, sql_backend, multi_entry_factory):
        for e in multi_entry_factory("user-Q", 6):
            sql_backend.save_session(e)
        page2 = sql_backend.get_sessions_by_user("user-Q", limit=4, offset=4)
        assert len(page2) == 2

    def test_date_filter(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        yesterday = datetime.utcnow() - timedelta(days=1)
        tomorrow  = datetime.utcnow() + timedelta(days=1)
        result = sql_backend.get_sessions_by_user(
            "user-42", start_date=yesterday, end_date=tomorrow
        )
        assert len(result) == 1

    def test_tag_filter(self, sql_backend, multi_entry_factory):
        entries = multi_entry_factory("user-T", 6)  # tags: tag-0, tag-1, tag-2
        for e in entries:
            sql_backend.save_session(e)
        result = sql_backend.get_sessions_by_user("user-T", tags=["tag-0"])
        assert len(result) == 2  # indices 0, 3

    def test_no_sessions_returns_empty_list(self, sql_backend):
        result = sql_backend.get_sessions_by_user("ghost-user")
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# search_sessions
# ─────────────────────────────────────────────────────────────────────────────

class TestSearchSessions:
    def test_keyword_found(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        results = sql_backend.search_sessions("user-42", "Python")
        assert len(results) == 1

    def test_keyword_case_insensitive(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        results = sql_backend.search_sessions("user-42", "python")
        assert len(results) == 1

    def test_keyword_not_found(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        results = sql_backend.search_sessions("user-42", "javascript")
        assert results == []

    def test_cross_user_isolation(self, sql_backend, sample_entry):
        """Search must not return sessions from other users."""
        sql_backend.save_session(sample_entry)  # user-42
        results = sql_backend.search_sessions("other-user", "Python")
        assert results == []


# ─────────────────────────────────────────────────────────────────────────────
# replay_session
# ─────────────────────────────────────────────────────────────────────────────

class TestReplaySession:
    def test_replay_returns_correct_structure(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        replay = sql_backend.replay_session(sample_entry.session_id)
        assert replay is not None
        assert replay.session_id == sample_entry.session_id
        assert replay.total_turns == 3
        assert len(replay.messages) == 3

    def test_replay_nonexistent_returns_none(self, sql_backend):
        assert sql_backend.replay_session("ghost-session") is None

    def test_replay_summary_populated(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        replay = sql_backend.replay_session(sample_entry.session_id)
        assert replay.summary is not None
        assert len(replay.summary) > 0


# ─────────────────────────────────────────────────────────────────────────────
# delete_session
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteSession:
    def test_delete_existing_returns_true(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        assert sql_backend.delete_session(sample_entry.session_id) is True

    def test_delete_removes_session(self, sql_backend, sample_entry):
        sql_backend.save_session(sample_entry)
        sql_backend.delete_session(sample_entry.session_id)
        assert sql_backend.get_session(sample_entry.session_id) is None

    def test_delete_nonexistent_returns_false(self, sql_backend):
        assert sql_backend.delete_session("ghost") is False
