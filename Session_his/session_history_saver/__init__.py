"""
session_history_saver
~~~~~~~~~~~~~~~~~~~~~
Track and persist user interaction history across sessions.

Quick-start::

    from session_history_saver import SessionTracker

    tracker = SessionTracker(backend="sqlite", db_path="./history.db")
    session = tracker.start_session(user_id="alice", project_id="my-app")
    tracker.add_user_message(session.session_id, "Hello!")
    tracker.add_assistant_message(session.session_id, "Hi there!")
    tracker.end_session(session.session_id)
"""

from .config import SessionHistoryConfig
from .exporters import (
    save_to_file,
    to_csv,
    to_json,
    to_jsonl,
    to_markdown,
    to_plain_text,
)
from .models import Message, MessageStatus, Role, Session
from .storage import BaseStorage, InMemoryStorage, JSONStorage, MongoDBStorage, SQLiteStorage
from .tracker import SessionTracker

__all__ = [
    "SessionTracker",
    "Session",
    "Message",
    "Role",
    "MessageStatus",
    "BaseStorage",
    "InMemoryStorage",
    "JSONStorage",
    "SQLiteStorage",
    "MongoDBStorage",
    "SessionHistoryConfig",
    "to_json",
    "to_jsonl",
    "to_csv",
    "to_markdown",
    "to_plain_text",
    "save_to_file",
]

__version__ = "1.0.0"