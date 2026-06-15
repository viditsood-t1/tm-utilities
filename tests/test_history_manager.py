"""
tests/test_history_manager.py
-------------------------------
Tests for the HistoryManager facade (backend-agnostic).
Runs the same scenarios against both SQL and Mongo backends via parametrize.
"""

import pytest
from consolidated_utility.history.manager import HistoryManager
from consolidated_utility.utils.models import MessageRole


# Parametrise across both managers defined in conftest
@pytest.fixture(params=["sql_manager", "mongo_manager"])
def manager(request):
    return request.getfixturevalue(request.param)


class TestCreateSession:
    def test_creates_session_with_messages(self, manager):
        from consolidated_utility.utils.models import Message
        msgs = [Message(role=MessageRole.USER, content="hi")]
        entry = manager.create_session("u1", messages=msgs)
        assert entry.session_id is not None
        assert entry.user_id == "u1"
        assert len(entry.messages) == 1

    def test_empty_session_allowed(self, manager):
        entry = manager.create_session("u2")
        assert entry.messages == []

    def test_tags_stored(self, manager):
        entry = manager.create_session("u3", tags=["beta"])
        fetched = manager.get_session(entry.session_id)
        assert "beta" in fetched.tags


class TestAddMessage:
    def test_add_message_increments_count(self, manager):
        entry = manager.create_session("u10")
        manager.add_message(entry.session_id, MessageRole.USER, "hello")
        updated = manager.get_session(entry.session_id)
        assert len(updated.messages) == 1

    def test_message_content_correct(self, manager):
        entry = manager.create_session("u11")
        manager.add_message(entry.session_id, MessageRole.ASSISTANT, "I can help")
        fetched = manager.get_session(entry.session_id)
        assert fetched.messages[0].content == "I can help"

    def test_multi_turn_conversation(self, manager):
        entry = manager.create_session("u12")
        turns = [
            (MessageRole.USER,      "What is Python?"),
            (MessageRole.ASSISTANT, "Python is a programming language."),
            (MessageRole.USER,      "Give me an example."),
            (MessageRole.ASSISTANT, "print('Hello World')"),
        ]
        for role, content in turns:
            manager.add_message(entry.session_id, role, content)
        fetched = manager.get_session(entry.session_id)
        assert len(fetched.messages) == 4


class TestGetUserHistory:
    def test_returns_all_user_sessions(self, manager, multi_entry_factory):
        for e in multi_entry_factory("hist-user", 3):
            manager.save_session(e)
        sessions = manager.get_user_history("hist-user")
        assert len(sessions) == 3

    def test_pagination(self, manager, multi_entry_factory):
        for e in multi_entry_factory("page-user", 5):
            manager.save_session(e)
        page = manager.get_user_history("page-user", limit=2, offset=2)
        assert len(page) == 2


class TestSearch:
    def test_finds_matching_session(self, manager, sample_entry):
        manager.save_session(sample_entry)
        results = manager.search("user-42", "Python")
        assert len(results) >= 1

    def test_no_match_empty_list(self, manager, sample_entry):
        manager.save_session(sample_entry)
        results = manager.search("user-42", "Fortran")
        assert results == []


class TestReplay:
    def test_replay_session(self, manager, sample_entry):
        manager.save_session(sample_entry)
        replay = manager.replay(sample_entry.session_id)
        assert replay is not None
        assert replay.total_turns == len(sample_entry.messages)

    def test_replay_nonexistent_returns_none(self, manager):
        assert manager.replay("does-not-exist") is None


class TestDeleteSession:
    def test_delete_then_get_returns_none(self, manager, sample_entry):
        manager.save_session(sample_entry)
        manager.delete_session(sample_entry.session_id)
        assert manager.get_session(sample_entry.session_id) is None


class TestContextManager:
    def test_context_manager_closes_gracefully(self, sql_backend):
        with HistoryManager(backend=sql_backend) as mgr:
            e = mgr.create_session("ctx-user")
            assert e is not None
        # No exception raised on close
