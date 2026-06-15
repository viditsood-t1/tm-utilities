"""
consolidated_utility.history.manager
--------------------------------------
High-level facade over any BaseHistoryBackend.

HistoryManager is the single entry-point developers should use.  It handles:
  • Backend selection (SQL vs Mongo) via BackendType enum or DSN auto-detection
  • Structured logging of every operation
  • Graceful error handling with descriptive messages
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union

from consolidated_utility.history.base import BaseHistoryBackend
from consolidated_utility.history.mongo_backend import MongoHistoryBackend
from consolidated_utility.history.sql_backend import SQLHistoryBackend
from consolidated_utility.logging import AuditLogger
from consolidated_utility.utils.models import (
    BackendType, HistoryEntry, Message, MessageRole, SessionReplay,
)


class HistoryManager:
    """
    Unified interface for session history across backends.

    Parameters
    ----------
    backend : BackendType | str
        ``BackendType.POSTGRESQL`` / ``BackendType.MONGODB``,
        or a raw DSN string (``"mongodb://..."`` / ``"postgresql://..."``).
    **kwargs
        Forwarded to the backend constructor.

    Examples
    --------
    >>> # PostgreSQL
    >>> mgr = HistoryManager(BackendType.POSTGRESQL,
    ...                      dsn="postgresql+psycopg2://user:pass@localhost/db")
    >>> # MongoDB
    >>> mgr = HistoryManager(BackendType.MONGODB,
    ...                      uri="mongodb://localhost:27017", db_name="mydb")
    >>> # Auto-detect from DSN string
    >>> mgr = HistoryManager("mongodb://localhost:27017/mydb")
    """

    def __init__(
        self,
        backend: Union[BackendType, str, BaseHistoryBackend],
        **kwargs,
    ) -> None:
        if isinstance(backend, BaseHistoryBackend):
            self._backend: BaseHistoryBackend = backend
        elif isinstance(backend, BackendType) or isinstance(backend, str):
            self._backend = self._build_backend(backend, **kwargs)
        else:
            raise TypeError(f"Unsupported backend type: {type(backend)}")

        self._log = AuditLogger("history.manager")

    # ── Backend factory ───────────────────────────────────────────────────────

    @staticmethod
    def _build_backend(
        backend: Union[BackendType, str],
        **kwargs,
    ) -> BaseHistoryBackend:
        if isinstance(backend, str):
            if backend.startswith("mongodb"):
                return MongoHistoryBackend(uri=backend, **kwargs)
            return SQLHistoryBackend(dsn=backend, **kwargs)

        if backend == BackendType.MONGODB:
            return MongoHistoryBackend(**kwargs)
        return SQLHistoryBackend(**kwargs)

    # ── Session lifecycle ─────────────────────────────────────────────────────

    def create_session(
        self,
        user_id:  str,
        messages: Optional[List[Message]] = None,
        tags:     Optional[List[str]]     = None,
        metadata: Optional[dict]          = None,
    ) -> HistoryEntry:
        """Create and persist a new session, optionally pre-populated with messages."""
        entry = HistoryEntry(
            user_id=user_id,
            messages=messages or [],
            tags=tags or [],
            metadata=metadata or {},
        )
        self._log.info("Creating session",
                       extra={"session_id": entry.session_id, "user_id": user_id})
        return self._backend.save_session(entry)

    def add_message(
        self,
        session_id: str,
        role:       MessageRole,
        content:    str,
        metadata:   Optional[dict] = None,
    ) -> HistoryEntry:
        """Append a single message to an existing session."""
        msg = Message(role=role, content=content, metadata=metadata or {})
        stub = HistoryEntry(user_id="", messages=[msg])  # user_id unused by append
        return self._backend.append_messages(session_id, stub)

    def save_session(self, entry: HistoryEntry) -> HistoryEntry:
        """Persist a fully-formed HistoryEntry (upsert)."""
        return self._backend.save_session(entry)

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def get_session(self, session_id: str) -> Optional[HistoryEntry]:
        """Fetch a single session."""
        self._log.info("Fetching session", extra={"session_id": session_id})
        return self._backend.get_session(session_id)

    def get_user_history(
        self,
        user_id:    str,
        limit:      int            = 20,
        offset:     int            = 0,
        start_date: Optional[datetime] = None,
        end_date:   Optional[datetime] = None,
        tags:       Optional[List[str]] = None,
    ) -> List[HistoryEntry]:
        """
        Return paginated session history for a user.

        Parameters
        ----------
        user_id    : Target user.
        limit      : Max sessions to return.
        offset     : Skip this many sessions (for pagination).
        start_date : Inclusive lower bound on ``created_at``.
        end_date   : Inclusive upper bound on ``created_at``.
        tags       : Return only sessions with at least one matching tag.
        """
        self._log.info("Fetching user history",
                       extra={"user_id": user_id, "limit": limit, "offset": offset})
        return self._backend.get_sessions_by_user(
            user_id, limit, offset, start_date, end_date, tags
        )

    def search(self, user_id: str, keyword: str, limit: int = 20) -> List[HistoryEntry]:
        """Search session messages by keyword."""
        self._log.info("Searching sessions",
                       extra={"user_id": user_id, "keyword": keyword})
        return self._backend.search_sessions(user_id, keyword, limit)

    # ── Replay ────────────────────────────────────────────────────────────────

    def replay(self, session_id: str) -> Optional[SessionReplay]:
        """
        Load a session and return it as a ``SessionReplay`` object,
        ready to be fed back into an agent or rendered in a UI.
        """
        self._log.info("Replaying session", extra={"session_id": session_id})
        replay = self._backend.replay_session(session_id)
        if replay:
            self._log.info("Replay ready",
                           extra={"session_id": session_id,
                                  "total_turns": replay.total_turns})
        return replay

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_session(self, session_id: str) -> bool:
        """Permanently remove a session."""
        return self._backend.delete_session(session_id)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Release backend resources."""
        self._backend.close()

    def __enter__(self) -> "HistoryManager":
        return self

    def __exit__(self, *_) -> None:
        self.close()
