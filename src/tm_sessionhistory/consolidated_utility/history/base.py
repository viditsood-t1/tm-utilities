"""
consolidated_utility.history.base
-----------------------------------
Abstract interface every storage backend must implement.
Coding to this interface means the rest of the package is backend-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from consolidated_utility.utils.models import HistoryEntry, SessionReplay


class BaseHistoryBackend(ABC):
    """Storage-agnostic contract for history persistence."""

    # ── Write ────────────────────────────────────────────────────────────────

    @abstractmethod
    def save_session(self, entry: HistoryEntry) -> HistoryEntry:
        """Persist a new session or overwrite an existing one."""

    @abstractmethod
    def append_messages(self, session_id: str, entry: HistoryEntry) -> HistoryEntry:
        """Append new messages to an existing session."""

    # ── Read ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[HistoryEntry]:
        """Return a single session by its ID, or None if not found."""

    @abstractmethod
    def get_sessions_by_user(
        self,
        user_id:    str,
        limit:      int            = 20,
        offset:     int            = 0,
        start_date: Optional[datetime] = None,
        end_date:   Optional[datetime] = None,
        tags:       Optional[List[str]] = None,
    ) -> List[HistoryEntry]:
        """Return paginated sessions for a user with optional filters."""

    @abstractmethod
    def search_sessions(
        self,
        user_id:  str,
        keyword:  str,
        limit:    int = 20,
    ) -> List[HistoryEntry]:
        """Full-text search across message content for a user."""

    # ── Replay ───────────────────────────────────────────────────────────────

    @abstractmethod
    def replay_session(self, session_id: str) -> Optional[SessionReplay]:
        """Load and return a structured replay of a session."""

    # ── Delete ───────────────────────────────────────────────────────────────

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Hard-delete a session. Returns True if a record was removed."""

    # ── Lifecycle ────────────────────────────────────────────────────────────

    @abstractmethod
    def close(self) -> None:
        """Release any held connections / handles."""
