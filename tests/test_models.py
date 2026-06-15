"""
tests/test_models.py
---------------------
Unit tests for shared Pydantic models.
"""

import pytest
from datetime import datetime

from consolidated_utility.utils.models import (
    BackendType, HistoryEntry, Message, MessageRole, SessionReplay,
)


class TestMessage:
    def test_defaults(self):
        msg = Message(role=MessageRole.USER, content="hello")
        assert isinstance(msg.timestamp, datetime)
        assert msg.metadata == {}

    def test_role_values(self):
        for role in MessageRole:
            msg = Message(role=role, content="x")
            assert msg.role == role


class TestHistoryEntry:
    def test_auto_session_id(self):
        e1 = HistoryEntry(user_id="u1")
        e2 = HistoryEntry(user_id="u1")
        assert e1.session_id != e2.session_id

    def test_messages_default_empty(self):
        e = HistoryEntry(user_id="u1")
        assert e.messages == []

    def test_tags_and_metadata_default(self):
        e = HistoryEntry(user_id="u1")
        assert e.tags == []
        assert e.metadata == {}

    def test_custom_session_id(self):
        e = HistoryEntry(session_id="my-id", user_id="u1")
        assert e.session_id == "my-id"


class TestSessionReplay:
    def test_replay_fields(self):
        msgs = [Message(role=MessageRole.USER, content="hi")]
        replay = SessionReplay(
            session_id="s1",
            user_id="u1",
            total_turns=1,
            messages=msgs,
        )
        assert replay.total_turns == 1
        assert replay.summary is None  # optional field
        assert isinstance(replay.replayed_at, datetime)


class TestBackendType:
    def test_enum_values(self):
        assert BackendType.POSTGRESQL == "postgresql"
        assert BackendType.MONGODB    == "mongodb"
