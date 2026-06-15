"""
Storage backends for session history persistence.
Supported: InMemory, JSON file, SQLite, MongoDB
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Message, Session


# ─────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────

class BaseStorage(ABC):
    """Abstract base class for all storage backends."""

    @abstractmethod
    def save_session(self, session: Session) -> None:
        """Persist (create or update) a session."""

    @abstractmethod
    def load_session(self, session_id: str) -> Optional[Session]:
        """Load a session by ID. Returns None if not found."""

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if deleted."""

    @abstractmethod
    def list_sessions(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Session]:
        """List sessions with optional filters."""

    @abstractmethod
    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""

    def append_message(self, session_id: str, message: Message) -> bool:
        """
        Append a single message to an existing session.
        Falls back to load → add → save.  Backends can override for efficiency.
        """
        session = self.load_session(session_id)
        if session is None:
            return False
        session.add_message(message)
        self.save_session(session)
        return True

    def count_sessions(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> int:
        """Return total session count matching optional filters."""
        return len(self.list_sessions(user_id=user_id, project_id=project_id, limit=10_000))

    def search_sessions(self, query: str, limit: int = 20) -> List[Session]:
        """Full-text search across message content (naive default)."""
        results = []
        for session in self.list_sessions(limit=10_000):
            for msg in session.messages:
                if query.lower() in msg.content.lower():
                    results.append(session)
                    break
            if len(results) >= limit:
                break
        return results


# ─────────────────────────────────────────────
# In-Memory
# ─────────────────────────────────────────────

class InMemoryStorage(BaseStorage):
    """
    Volatile in-memory storage.
    Useful for testing, short-lived scripts, or as a write-through cache.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def save_session(self, session: Session) -> None:
        with self._lock:
            self._store[session.session_id] = session

    def load_session(self, session_id: str) -> Optional[Session]:
        return self._store.get(session_id)

    def append_message(self, session_id: str, message: Message) -> bool:
        """
        In-memory override: append the message to the stored Session object directly.
        If the tracker has already mutated it (via add_message on the cached ref),
        this is a no-op duplicate guard based on message_id.
        """
        with self._lock:
            session = self._store.get(session_id)
            if session is None:
                return False
            # Dedup: skip if this exact message_id is already present
            existing_ids = {m.message_id for m in session.messages}
            if message.message_id not in existing_ids:
                session.add_message(message)
            return True

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            return self._store.pop(session_id, None) is not None

    def list_sessions(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Session]:
        sessions = list(self._store.values())
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        if project_id:
            sessions = [s for s in sessions if s.project_id == project_id]
        if tags:
            sessions = [s for s in sessions if any(t in s.tags for t in tags)]
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[offset: offset + limit]

    def session_exists(self, session_id: str) -> bool:
        return session_id in self._store

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# ─────────────────────────────────────────────
# JSON File
# ─────────────────────────────────────────────

class JSONStorage(BaseStorage):
    """
    Persist sessions as individual JSON files inside a directory.

    Directory layout::

        storage_dir/
            <session_id>.json
            <session_id>.json
            ...
    """

    def __init__(self, storage_dir: str = "./session_history", indent: int = 2) -> None:
        self.storage_dir = Path(storage_dir)
        self.indent = indent
        self._lock = threading.Lock()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self.storage_dir / f"{session_id}.json"

    def save_session(self, session: Session) -> None:
        data = session.to_dict()
        with self._lock:
            with open(self._path(session.session_id), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=self.indent, ensure_ascii=False)

    def load_session(self, session_id: str) -> Optional[Session]:
        path = self._path(session_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Session.from_dict(data)

    def delete_session(self, session_id: str) -> bool:
        path = self._path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_sessions(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Session]:
        sessions: List[Session] = []
        for p in sorted(self.storage_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Filter before constructing full Session object
            if user_id and data.get("user_id") != user_id:
                continue
            if project_id and data.get("project_id") != project_id:
                continue
            if tags and not any(t in data.get("tags", []) for t in tags):
                continue
            sessions.append(Session.from_dict(data))

        return sessions[offset: offset + limit]

    def session_exists(self, session_id: str) -> bool:
        return self._path(session_id).exists()


# ─────────────────────────────────────────────
# SQLite
# ─────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    user_id      TEXT,
    project_id   TEXT,
    title        TEXT,
    tags         TEXT,          -- JSON array
    metadata     TEXT,          -- JSON object
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    message_count INTEGER DEFAULT 0,
    total_tokens  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    message_id   TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    role         TEXT NOT NULL,
    content      TEXT NOT NULL,
    timestamp    TEXT NOT NULL,
    metadata     TEXT,
    status       TEXT,
    tokens       INTEGER,
    model        TEXT,
    latency_ms   REAL,
    sort_order   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_sessions_user    ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
"""


class SQLiteStorage(BaseStorage):
    """
    Persist sessions in a SQLite database.
    Thread-safe via connection-per-thread (check_same_thread=False + lock).
    """

    def __init__(self, db_path: str = "./session_history.db") -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # ── helpers ──────────────────────────────

    @staticmethod
    def _row_to_session(row: sqlite3.Row, message_rows: List[sqlite3.Row]) -> Session:
        session = Session(
            session_id=row["session_id"],
            user_id=row["user_id"],
            project_id=row["project_id"],
            title=row["title"],
            tags=json.loads(row["tags"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
        for mr in message_rows:
            session.messages.append(Message(
                message_id=mr["message_id"],
                role=mr["role"],
                content=mr["content"],
                timestamp=datetime.fromisoformat(mr["timestamp"]),
                metadata=json.loads(mr["metadata"] or "{}"),
                status=mr["status"],
                tokens=mr["tokens"],
                model=mr["model"],
                latency_ms=mr["latency_ms"],
            ))
        return session

    # ── BaseStorage impl ──────────────────────

    def save_session(self, session: Session) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO sessions
                        (session_id, user_id, project_id, title, tags, metadata,
                         created_at, updated_at, message_count, total_tokens)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        user_id=excluded.user_id,
                        project_id=excluded.project_id,
                        title=excluded.title,
                        tags=excluded.tags,
                        metadata=excluded.metadata,
                        updated_at=excluded.updated_at,
                        message_count=excluded.message_count,
                        total_tokens=excluded.total_tokens
                    """,
                    (
                        session.session_id,
                        session.user_id,
                        session.project_id,
                        session.title,
                        json.dumps(session.tags),
                        json.dumps(session.metadata),
                        session.created_at.isoformat(),
                        session.updated_at.isoformat(),
                        session.message_count,
                        session.total_tokens,
                    ),
                )
                # Replace all messages for this session
                conn.execute("DELETE FROM messages WHERE session_id=?", (session.session_id,))
                for idx, msg in enumerate(session.messages):
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO messages
                            (message_id, session_id, role, content, timestamp,
                             metadata, status, tokens, model, latency_ms, sort_order)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            msg.message_id,
                            session.session_id,
                            msg.role,
                            msg.content,
                            msg.timestamp.isoformat(),
                            json.dumps(msg.metadata),
                            msg.status,
                            msg.tokens,
                            msg.model,
                            msg.latency_ms,
                            idx,
                        ),
                    )

    def load_session(self, session_id: str) -> Optional[Session]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            if row is None:
                return None
            msg_rows = conn.execute(
                "SELECT * FROM messages WHERE session_id=? ORDER BY sort_order", (session_id,)
            ).fetchall()
        return self._row_to_session(row, msg_rows)

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "DELETE FROM sessions WHERE session_id=?", (session_id,)
                )
                return cur.rowcount > 0

    def list_sessions(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Session]:
        where, params = [], []
        if user_id:
            where.append("user_id=?"); params.append(user_id)
        if project_id:
            where.append("project_id=?"); params.append(project_id)

        sql = "SELECT * FROM sessions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params += [limit, offset]

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            sessions = []
            for row in rows:
                if tags:
                    row_tags = json.loads(row["tags"] or "[]")
                    if not any(t in row_tags for t in tags):
                        continue
                msg_rows = conn.execute(
                    "SELECT * FROM messages WHERE session_id=? ORDER BY sort_order",
                    (row["session_id"],),
                ).fetchall()
                sessions.append(self._row_to_session(row, msg_rows))
        return sessions

    def session_exists(self, session_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        return row is not None

    def append_message(self, session_id: str, message: Message) -> bool:
        """Optimized single-message append without rewriting all messages."""
        with self._lock:
            with self._connect() as conn:
                if not self.session_exists(session_id):
                    return False
                count = conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id=?", (session_id,)
                ).fetchone()[0]
                conn.execute(
                    """
                    INSERT INTO messages
                        (message_id, session_id, role, content, timestamp,
                         metadata, status, tokens, model, latency_ms, sort_order)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        message.message_id,
                        session_id,
                        message.role,
                        message.content,
                        message.timestamp.isoformat(),
                        json.dumps(message.metadata),
                        message.status,
                        message.tokens,
                        message.model,
                        message.latency_ms,
                        count,
                    ),
                )
                conn.execute(
                    "UPDATE sessions SET updated_at=?, message_count=message_count+1 WHERE session_id=?",
                    (datetime.now(timezone.utc).isoformat(), session_id),
                )
        return True

    def search_sessions(self, query: str, limit: int = 20) -> List[Session]:
        """SQLite FTS-style search on message content."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT s.session_id
                FROM sessions s
                JOIN messages m ON m.session_id = s.session_id
                WHERE m.content LIKE ?
                ORDER BY s.updated_at DESC
                LIMIT ?
                """,
                (f"%{query}%", limit),
            ).fetchall()
        return [self.load_session(r["session_id"]) for r in rows if self.load_session(r["session_id"])]


# ─────────────────────────────────────────────
# MongoDB
# ─────────────────────────────────────────────

class MongoDBStorage(BaseStorage):
    """
    Persist sessions in a MongoDB collection.

    Requires ``pymongo``::

        pip install pymongo
        # or with DNS SRV support (Atlas):
        pip install "pymongo[srv]"

    Parameters
    ----------
    uri : str
        MongoDB connection URI.
        Examples:
          - Local:  ``mongodb://localhost:27017``
          - Atlas:  ``mongodb+srv://user:pass@cluster.mongodb.net``
          - Auth:   ``mongodb://user:pass@host:27017/dbname``
    db_name : str
        Database name (default: ``session_history``).
    collection_name : str
        Collection name (default: ``sessions``).
    server_selection_timeout_ms : int
        Timeout in ms for server selection (default: 5000).

    Environment variable shortcuts (override constructor args):
        ``SHS_MONGO_URI``        — connection URI
        ``SHS_MONGO_DB``         — database name
        ``SHS_MONGO_COLLECTION`` — collection name
    """

    def __init__(
        self,
        uri: str = "mongodb://localhost:27017",
        db_name: str = "session_history",
        collection_name: str = "sessions",
        server_selection_timeout_ms: int = 5000,
    ) -> None:
        try:
            from pymongo import MongoClient, ASCENDING, DESCENDING
            from pymongo.errors import ConnectionFailure
        except ImportError:
            raise ImportError(
                "pymongo is required for MongoDBStorage.\n"
                "Install it with:  pip install pymongo\n"
                "For MongoDB Atlas: pip install 'pymongo[srv]'"
            )

        # Env var overrides
        uri = os.getenv("SHS_MONGO_URI", uri)
        db_name = os.getenv("SHS_MONGO_DB", db_name)
        collection_name = os.getenv("SHS_MONGO_COLLECTION", collection_name)

        self._client = MongoClient(
            uri,
            serverSelectionTimeoutMS=server_selection_timeout_ms,
        )
        self._db = self._client[db_name]
        self._col = self._db[collection_name]

        # Ensure indexes
        self._col.create_index("session_id", unique=True)
        self._col.create_index("user_id")
        self._col.create_index("project_id")
        self._col.create_index([("updated_at", DESCENDING)])
        self._col.create_index("tags")

    # ── helpers ──────────────────────────────────

    @staticmethod
    def _session_to_doc(session: Session) -> dict:
        """Convert Session → MongoDB document."""
        doc = session.to_dict()
        # MongoDB uses _id; keep session_id as the primary key field too
        doc["_id"] = session.session_id
        return doc

    @staticmethod
    def _doc_to_session(doc: dict) -> Session:
        """Convert MongoDB document → Session."""
        data = {k: v for k, v in doc.items() if k != "_id"}
        return Session.from_dict(data)

    # ── BaseStorage impl ──────────────────────────

    def save_session(self, session: Session) -> None:
        doc = self._session_to_doc(session)
        self._col.replace_one(
            {"_id": session.session_id},
            doc,
            upsert=True,
        )

    def load_session(self, session_id: str) -> Optional[Session]:
        doc = self._col.find_one({"_id": session_id})
        if doc is None:
            return None
        return self._doc_to_session(doc)

    def delete_session(self, session_id: str) -> bool:
        result = self._col.delete_one({"_id": session_id})
        return result.deleted_count > 0

    def session_exists(self, session_id: str) -> bool:
        return self._col.count_documents({"_id": session_id}, limit=1) > 0

    def list_sessions(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Session]:
        query: Dict[str, Any] = {}
        if user_id:
            query["user_id"] = user_id
        if project_id:
            query["project_id"] = project_id
        if tags:
            query["tags"] = {"$in": tags}

        cursor = (
            self._col
            .find(query, sort=[("updated_at", -1)])
            .skip(offset)
            .limit(limit)
        )
        return [self._doc_to_session(doc) for doc in cursor]

    def append_message(self, session_id: str, message: Message) -> bool:
        """
        Atomically push a single message into the embedded messages array
        and update the session's updated_at / message_count counters.
        """
        result = self._col.update_one(
            {"_id": session_id},
            {
                "$push": {"messages": message.to_dict()},
                "$inc": {"message_count": 1},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            },
        )
        return result.matched_count > 0

    def search_sessions(self, query: str, limit: int = 20) -> List[Session]:
        """
        Search message content using MongoDB regex.
        For production workloads consider creating a text index:
            db.sessions.create_index([("messages.content", "text")])
        and using $text search instead.
        """
        cursor = self._col.find(
            {"messages.content": {"$regex": query, "$options": "i"}},
            sort=[("updated_at", -1)],
            limit=limit,
        )
        return [self._doc_to_session(doc) for doc in cursor]

    def count_sessions(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> int:
        query: Dict[str, Any] = {}
        if user_id:
            query["user_id"] = user_id
        if project_id:
            query["project_id"] = project_id
        return self._col.count_documents(query)

    def close(self) -> None:
        """Close the MongoDB connection."""
        self._client.close()

    def __enter__(self) -> "MongoDBStorage":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
