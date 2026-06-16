"""
tests/conftest.py
------------------
Shared pytest fixtures.

SQL tests  → SQLite in-memory  (no external DB required)
Mongo tests → mongomock         (no external Mongo required)
"""

import pytest
import mongomock
from unittest.mock import patch

from consolidated_utility.history.sql_backend import SQLHistoryBackend
from consolidated_utility.history.mongo_backend import MongoHistoryBackend
from consolidated_utility.history.manager import HistoryManager
from consolidated_utility.utils.models import (
    HistoryEntry, Message, MessageRole,
)


# ── SQL (SQLite in-memory) ───────────────────────────────────────────────────

@pytest.fixture()
def sql_backend():
    backend = SQLHistoryBackend(dsn="sqlite:///:memory:")
    yield backend
    backend.close()


@pytest.fixture()
def sql_manager(sql_backend):
    return HistoryManager(backend=sql_backend)


# ── MongoDB (mongomock) ──────────────────────────────────────────────────────

@pytest.fixture()
def mongo_backend():
    with patch("consolidated_utility.history.mongo_backend.MongoClient",
               mongomock.MongoClient):
        backend = MongoHistoryBackend(
            uri="mongodb://localhost:27017",
            db_name="test_db",
            collection="sessions",
        )
        yield backend
        backend.close()


@pytest.fixture()
def mongo_manager(mongo_backend):
    return HistoryManager(backend=mongo_backend)


# ── Sample data helpers ──────────────────────────────────────────────────────

@pytest.fixture()
def sample_entry() -> HistoryEntry:
    return HistoryEntry(
        session_id="sess-001",
        user_id="user-42",
        messages=[
            Message(role=MessageRole.USER,      content="Hello, how are you?"),
            Message(role=MessageRole.ASSISTANT, content="I'm great! How can I help?"),
            Message(role=MessageRole.USER,      content="Tell me about Python."),
        ],
        tags=["onboarding", "python"],
        metadata={"source": "web"},
    )


@pytest.fixture()
def multi_entry_factory():
    """Return a factory that produces n distinct entries for a given user_id."""
    def _make(user_id: str, n: int) -> list:
        entries = []
        for i in range(n):
            entries.append(HistoryEntry(
                session_id=f"sess-{user_id}-{i}",
                user_id=user_id,
                messages=[
                    Message(role=MessageRole.USER,
                            content=f"Question {i} about topic-{i}"),
                    Message(role=MessageRole.ASSISTANT,
                            content=f"Answer {i}"),
                ],
                tags=[f"tag-{i % 3}"],
            ))
        return entries
    return _make
