"""
tests/test_mongo_backend.py
-----------------------------
Full test coverage for MongoHistoryBackend using mongomock.
"""

import pytest
from datetime import datetime, timedelta

from consolidated_utility.utils.models import HistoryEntry, Message, MessageRole


class TestSaveAndGet:
    def test_save_and_retrieve(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        fetched = mongo_backend.get_session(sample_entry.session_id)
        assert fetched is not None
        assert fetched.session_id == sample_entry.session_id

    def test_get_nonexistent_returns_none(self, mongo_backend):
        assert mongo_backend.get_session("no-such-id") is None

    def test_messages_round_trip(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        fetched = mongo_backend.get_session(sample_entry.session_id)
        assert len(fetched.messages) == 3
        assert fetched.messages[1].role == MessageRole.ASSISTANT

    def test_tags_persisted(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        fetched = mongo_backend.get_session(sample_entry.session_id)
        assert "onboarding" in fetched.tags

    def test_metadata_persisted(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        fetched = mongo_backend.get_session(sample_entry.session_id)
        assert fetched.metadata["source"] == "web"

    def test_upsert_replaces_messages(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        sample_entry.messages = [Message(role=MessageRole.USER, content="only this")]
        mongo_backend.save_session(sample_entry)
        fetched = mongo_backend.get_session(sample_entry.session_id)
        assert len(fetched.messages) == 1


class TestAppendMessages:
    def test_append_increases_message_count(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        new = HistoryEntry(
            user_id=sample_entry.user_id,
            messages=[Message(role=MessageRole.USER, content="appended")],
        )
        updated = mongo_backend.append_messages(sample_entry.session_id, new)
        assert len(updated.messages) == 4

    def test_append_updates_updated_at(self, mongo_backend, sample_entry):
        import time
        mongo_backend.save_session(sample_entry)
        before = sample_entry.updated_at
        time.sleep(0.01)  # ensure clock advances
        new = HistoryEntry(
            user_id=sample_entry.user_id,
            messages=[Message(role=MessageRole.ASSISTANT, content="new answer")],
        )
        updated = mongo_backend.append_messages(sample_entry.session_id, new)
        assert updated.updated_at >= before


class TestGetSessionsByUser:
    def test_returns_sessions_for_correct_user(
        self, mongo_backend, multi_entry_factory
    ):
        for e in multi_entry_factory("mongo-user-1", 4):
            mongo_backend.save_session(e)
        for e in multi_entry_factory("mongo-user-2", 2):
            mongo_backend.save_session(e)

        results = mongo_backend.get_sessions_by_user("mongo-user-1")
        assert len(results) == 4
        assert all(e.user_id == "mongo-user-1" for e in results)

    def test_limit_respected(self, mongo_backend, multi_entry_factory):
        for e in multi_entry_factory("user-lim", 8):
            mongo_backend.save_session(e)
        results = mongo_backend.get_sessions_by_user("user-lim", limit=3)
        assert len(results) == 3

    def test_offset_pagination(self, mongo_backend, multi_entry_factory):
        for e in multi_entry_factory("user-off", 5):
            mongo_backend.save_session(e)
        page2 = mongo_backend.get_sessions_by_user("user-off", limit=3, offset=3)
        assert len(page2) == 2

    def test_tag_filter(self, mongo_backend, multi_entry_factory):
        entries = multi_entry_factory("user-tag", 6)
        for e in entries:
            mongo_backend.save_session(e)
        # tag-0 assigned to indices 0, 3
        results = mongo_backend.get_sessions_by_user("user-tag", tags=["tag-0"])
        assert all("tag-0" in e.tags for e in results)

    def test_date_filter(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        future = datetime.utcnow() + timedelta(days=1)
        past   = datetime.utcnow() - timedelta(days=1)
        in_range = mongo_backend.get_sessions_by_user(
            "user-42", start_date=past, end_date=future
        )
        assert len(in_range) == 1
        out_range = mongo_backend.get_sessions_by_user(
            "user-42", end_date=past - timedelta(seconds=1)
        )
        assert len(out_range) == 0

    def test_empty_result_for_unknown_user(self, mongo_backend):
        assert mongo_backend.get_sessions_by_user("nobody") == []


class TestSearchSessions:
    def test_search_by_keyword(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        results = mongo_backend.search_sessions("user-42", "Python")
        assert len(results) == 1

    def test_search_no_match(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        results = mongo_backend.search_sessions("user-42", "Kubernetes")
        assert results == []

    def test_search_user_isolation(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        results = mongo_backend.search_sessions("wrong-user", "Python")
        assert results == []


class TestReplaySession:
    def test_replay_structure(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        replay = mongo_backend.replay_session(sample_entry.session_id)
        assert replay is not None
        assert replay.total_turns == 3
        assert replay.session_id == sample_entry.session_id

    def test_replay_nonexistent(self, mongo_backend):
        assert mongo_backend.replay_session("ghost") is None

    def test_replay_message_order(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        replay = mongo_backend.replay_session(sample_entry.session_id)
        roles = [m.role for m in replay.messages]
        assert roles[0] == MessageRole.USER
        assert roles[1] == MessageRole.ASSISTANT


class TestDeleteSession:
    def test_delete_existing(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        assert mongo_backend.delete_session(sample_entry.session_id) is True

    def test_delete_removes_document(self, mongo_backend, sample_entry):
        mongo_backend.save_session(sample_entry)
        mongo_backend.delete_session(sample_entry.session_id)
        assert mongo_backend.get_session(sample_entry.session_id) is None

    def test_delete_nonexistent_returns_false(self, mongo_backend):
        assert mongo_backend.delete_session("no-such-id") is False
