"""
consolidated_utility.history.sql_backend
------------------------------------------
PostgreSQL-backed history storage using SQLAlchemy Core (no ORM overhead).

Schema
------
  sessions  — one row per session (session_id PK, user_id, created_at, updated_at,
               tags JSONB, metadata JSONB)
  messages  — one row per message, FK → sessions.session_id
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, MetaData, String, Table, Text,
    create_engine, text,
)
from sqlalchemy import JSON as SAJSON
from sqlalchemy.engine import Connection, Engine

from consolidated_utility.history.base import BaseHistoryBackend
from consolidated_utility.logging import get_logger
from consolidated_utility.utils.models import HistoryEntry, Message, MessageRole, SessionReplay

_log = get_logger("history.sql")

# ── Schema definition ────────────────────────────────────────────────────────

_metadata = MetaData()

sessions_table = Table(
    "sessions", _metadata,
    Column("session_id",  String(64),  primary_key=True),
    Column("user_id",     String(64),  nullable=False, index=True),
    Column("created_at",  DateTime,    nullable=False),
    Column("updated_at",  DateTime,    nullable=False),
    Column("tags",        SAJSON,      nullable=False, default=list),
    Column("metadata",    SAJSON,      nullable=False, default=dict),
)

messages_table = Table(
    "messages", _metadata,
    Column("id",          Integer,     primary_key=True, autoincrement=True),
    Column("session_id",  String(64),  ForeignKey("sessions.session_id", ondelete="CASCADE"),
                          nullable=False, index=True),
    Column("role",        String(16),  nullable=False),
    Column("content",     Text,        nullable=False),
    Column("timestamp",   DateTime,    nullable=False),
    Column("metadata",    SAJSON,      nullable=False, default=dict),
)


class SQLHistoryBackend(BaseHistoryBackend):
    """
    Persist and retrieve session history in PostgreSQL (or any SQLAlchemy-
    compatible database, including SQLite for testing).

    Parameters
    ----------
    dsn : str
        SQLAlchemy connection string, e.g.
        ``"postgresql+psycopg2://user:pass@host/db"``
        ``"sqlite:///./test.db"``
    echo : bool
        Pass ``True`` to log every SQL statement (debug only).
    """

    def __init__(self, dsn: str, echo: bool = False) -> None:
        self._engine: Engine = create_engine(dsn, echo=echo, future=True)
        _metadata.create_all(self._engine)
        _log.info("SQLHistoryBackend initialised", extra={"dsn": dsn.split("@")[-1]})

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _conn(self) -> Connection:
        return self._engine.connect()

    @staticmethod
    def _row_to_entry(session_row: Any, message_rows: List[Any]) -> HistoryEntry:
        messages = [
            Message(
                role=MessageRole(r.role),
                content=r.content,
                timestamp=r.timestamp,
                metadata=r.metadata or {},
            )
            for r in message_rows
        ]
        return HistoryEntry(
            session_id=session_row.session_id,
            user_id=session_row.user_id,
            messages=messages,
            created_at=session_row.created_at,
            updated_at=session_row.updated_at,
            tags=session_row.tags or [],
            metadata=session_row.metadata or {},
        )

    def _fetch_messages(self, conn: Connection, session_id: str) -> List[Any]:
        result = conn.execute(
            messages_table.select()
            .where(messages_table.c.session_id == session_id)
            .order_by(messages_table.c.timestamp)
        )
        return result.fetchall()

    # ── Write ────────────────────────────────────────────────────────────────

    def save_session(self, entry: HistoryEntry) -> HistoryEntry:
        with self._conn() as conn:
            # Upsert session header
            existing = conn.execute(
                sessions_table.select()
                .where(sessions_table.c.session_id == entry.session_id)
            ).fetchone()

            now = datetime.utcnow()
            if existing:
                conn.execute(
                    sessions_table.update()
                    .where(sessions_table.c.session_id == entry.session_id)
                    .values(updated_at=now, tags=entry.tags, metadata=entry.metadata)
                )
                # Replace all messages
                conn.execute(
                    messages_table.delete()
                    .where(messages_table.c.session_id == entry.session_id)
                )
            else:
                conn.execute(sessions_table.insert().values(
                    session_id=entry.session_id,
                    user_id=entry.user_id,
                    created_at=entry.created_at or now,
                    updated_at=now,
                    tags=entry.tags,
                    metadata=entry.metadata,
                ))

            # Insert all messages
            if entry.messages:
                conn.execute(messages_table.insert(), [
                    dict(
                        session_id=entry.session_id,
                        role=m.role if isinstance(m.role, str) else m.role.value,
                        content=m.content,
                        timestamp=m.timestamp,
                        metadata=m.metadata,
                    )
                    for m in entry.messages
                ])
            conn.commit()

        _log.info("Session saved", extra={"session_id": entry.session_id,
                                           "messages": len(entry.messages)})
        return entry

    def append_messages(self, session_id: str, entry: HistoryEntry) -> HistoryEntry:
        with self._conn() as conn:
            now = datetime.utcnow()
            conn.execute(
                sessions_table.update()
                .where(sessions_table.c.session_id == session_id)
                .values(updated_at=now)
            )
            if entry.messages:
                conn.execute(messages_table.insert(), [
                    dict(
                        session_id=session_id,
                        role=m.role if isinstance(m.role, str) else m.role.value,
                        content=m.content,
                        timestamp=m.timestamp,
                        metadata=m.metadata,
                    )
                    for m in entry.messages
                ])
            conn.commit()
        return self.get_session(session_id)

    # ── Read ─────────────────────────────────────────────────────────────────

    def get_session(self, session_id: str) -> Optional[HistoryEntry]:
        with self._conn() as conn:
            s_row = conn.execute(
                sessions_table.select()
                .where(sessions_table.c.session_id == session_id)
            ).fetchone()
            if not s_row:
                return None
            m_rows = self._fetch_messages(conn, session_id)
        return self._row_to_entry(s_row, m_rows)

    def get_sessions_by_user(
        self,
        user_id:    str,
        limit:      int            = 20,
        offset:     int            = 0,
        start_date: Optional[datetime] = None,
        end_date:   Optional[datetime] = None,
        tags:       Optional[List[str]] = None,
    ) -> List[HistoryEntry]:
        stmt = (
            sessions_table.select()
            .where(sessions_table.c.user_id == user_id)
            .order_by(sessions_table.c.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if start_date:
            stmt = stmt.where(sessions_table.c.created_at >= start_date)
        if end_date:
            stmt = stmt.where(sessions_table.c.created_at <= end_date)

        with self._conn() as conn:
            rows = conn.execute(stmt).fetchall()
            entries = []
            for row in rows:
                m_rows = self._fetch_messages(conn, row.session_id)
                e = self._row_to_entry(row, m_rows)
                # Tag filter (post-query; JSONB contains operator is DB-specific)
                if tags and not any(t in e.tags for t in tags):
                    continue
                entries.append(e)
        return entries

    def search_sessions(self, user_id: str, keyword: str, limit: int = 20) -> List[HistoryEntry]:
        """
        Simple LIKE search across message content.
        For production, replace with a full-text index.
        """
        with self._conn() as conn:
            rows = conn.execute(
                messages_table.select()
                .where(messages_table.c.content.ilike(f"%{keyword}%"))
                .limit(limit * 5)  # over-fetch before user filter
            ).fetchall()

            session_ids = list(dict.fromkeys(r.session_id for r in rows))

            entries = []
            for sid in session_ids[:limit]:
                s_row = conn.execute(
                    sessions_table.select()
                    .where(sessions_table.c.session_id == sid)
                    .where(sessions_table.c.user_id == user_id)
                ).fetchone()
                if s_row:
                    m_rows = self._fetch_messages(conn, sid)
                    entries.append(self._row_to_entry(s_row, m_rows))
        return entries

    # ── Replay ───────────────────────────────────────────────────────────────

    def replay_session(self, session_id: str) -> Optional[SessionReplay]:
        entry = self.get_session(session_id)
        if not entry:
            return None
        return SessionReplay(
            session_id=entry.session_id,
            user_id=entry.user_id,
            total_turns=len(entry.messages),
            messages=entry.messages,
            summary=f"Replaying {len(entry.messages)} messages from session {session_id}",
        )

    # ── Delete ───────────────────────────────────────────────────────────────

    def delete_session(self, session_id: str) -> bool:
        with self._conn() as conn:
            result = conn.execute(
                sessions_table.delete()
                .where(sessions_table.c.session_id == session_id)
            )
            conn.commit()
        deleted = result.rowcount > 0
        if deleted:
            _log.info("Session deleted", extra={"session_id": session_id})
        return deleted

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._engine.dispose()
        _log.info("SQLHistoryBackend connection pool disposed")
