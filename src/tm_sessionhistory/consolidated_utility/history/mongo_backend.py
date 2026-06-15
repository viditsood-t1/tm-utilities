"""
consolidated_utility.history.mongo_backend
--------------------------------------------
MongoDB-backed history storage using pymongo.

Document schema (collection: ``sessions``)
-------------------------------------------
{
  "_id":        "<session_id>",
  "user_id":    "...",
  "created_at": ISODate,
  "updated_at": ISODate,
  "tags":       [...],
  "metadata":   {...},
  "messages": [
    {"role": "user", "content": "...", "timestamp": ISODate, "metadata": {...}},
    ...
  ]
}
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Optional

from pymongo import MongoClient, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from consolidated_utility.history.base import BaseHistoryBackend
from consolidated_utility.logging import get_logger
from consolidated_utility.utils.models import HistoryEntry, Message, MessageRole, SessionReplay

_log = get_logger("history.mongo")


def _entry_to_doc(entry: HistoryEntry) -> Dict[str, Any]:
    return {
        "_id":        entry.session_id,
        "user_id":    entry.user_id,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
        "tags":       entry.tags,
        "metadata":   entry.metadata,
        "messages": [
            {
                "role":      m.role if isinstance(m.role, str) else m.role.value,
                "content":   m.content,
                "timestamp": m.timestamp,
                "metadata":  m.metadata,
            }
            for m in entry.messages
        ],
    }


def _doc_to_entry(doc: Dict[str, Any]) -> HistoryEntry:
    messages = [
        Message(
            role=MessageRole(m["role"]),
            content=m["content"],
            timestamp=m["timestamp"],
            metadata=m.get("metadata", {}),
        )
        for m in doc.get("messages", [])
    ]
    return HistoryEntry(
        session_id=doc["_id"],
        user_id=doc["user_id"],
        messages=messages,
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        tags=doc.get("tags", []),
        metadata=doc.get("metadata", {}),
    )


class MongoHistoryBackend(BaseHistoryBackend):
    """
    Persist and retrieve session history in MongoDB.

    Parameters
    ----------
    uri        : MongoDB connection URI.
    db_name    : Database name.
    collection : Collection name (default ``"sessions"``).
    """

    def __init__(
        self,
        uri:        str = "mongodb://localhost:27017",
        db_name:    str = "utility_db",
        collection: str = "sessions",
        **client_kwargs,
    ) -> None:
        self._client: MongoClient = MongoClient(uri, **client_kwargs)
        self._db: Database        = self._client[db_name]
        self._col: Collection     = self._db[collection]
        self._ensure_indexes()
        _log.info("MongoHistoryBackend initialised",
                  extra={"db": db_name, "collection": collection})

    def _ensure_indexes(self) -> None:
        self._col.create_index("user_id")
        self._col.create_index("updated_at")
        self._col.create_index("tags")
        self._col.create_index([("messages.content", "text")], sparse=True)

    # ── Write ────────────────────────────────────────────────────────────────

    def save_session(self, entry: HistoryEntry) -> HistoryEntry:
        doc = _entry_to_doc(entry)
        self._col.replace_one({"_id": entry.session_id}, doc, upsert=True)
        _log.info("Session saved",
                  extra={"session_id": entry.session_id, "messages": len(entry.messages)})
        return entry

    def append_messages(self, session_id: str, entry: HistoryEntry) -> HistoryEntry:
        new_msgs = [
            {
                "role":      m.role if isinstance(m.role, str) else m.role.value,
                "content":   m.content,
                "timestamp": m.timestamp,
                "metadata":  m.metadata,
            }
            for m in entry.messages
        ]
        self._col.update_one(
            {"_id": session_id},
            {
                "$push":  {"messages": {"$each": new_msgs}},
                "$set":   {"updated_at": datetime.utcnow()},
            },
        )
        return self.get_session(session_id)

    # ── Read ─────────────────────────────────────────────────────────────────

    def get_session(self, session_id: str) -> Optional[HistoryEntry]:
        doc = self._col.find_one({"_id": session_id})
        return _doc_to_entry(doc) if doc else None

    def get_sessions_by_user(
        self,
        user_id:    str,
        limit:      int            = 20,
        offset:     int            = 0,
        start_date: Optional[datetime] = None,
        end_date:   Optional[datetime] = None,
        tags:       Optional[List[str]] = None,
    ) -> List[HistoryEntry]:
        query: Dict[str, Any] = {"user_id": user_id}
        if start_date or end_date:
            query["created_at"] = {}
            if start_date:
                query["created_at"]["$gte"] = start_date
            if end_date:
                query["created_at"]["$lte"] = end_date
        if tags:
            query["tags"] = {"$in": tags}

        cursor = (
            self._col.find(query)
            .sort("updated_at", DESCENDING)
            .skip(offset)
            .limit(limit)
        )
        return [_doc_to_entry(doc) for doc in cursor]

    def search_sessions(self, user_id: str, keyword: str, limit: int = 20) -> List[HistoryEntry]:
        """
        Uses MongoDB text index on messages.content.
        Falls back to regex scan if the text index is unavailable.
        """
        try:
            raw_cursor = self._col.find(
                {"user_id": user_id, "$text": {"$search": keyword}},
                {"score": {"$meta": "textScore"}},
            )
            # textScore sort is not supported in all environments (e.g. mongomock);
            # attempt it but fall back to an unsorted cursor on failure.
            try:
                cursor = raw_cursor.sort([("score", {"$meta": "textScore"})]).limit(limit)
                # Force evaluation to surface any deferred sort errors
                docs = list(cursor)
            except Exception:
                docs = list(
                    self._col.find(
                        {"user_id": user_id, "$text": {"$search": keyword}}
                    ).limit(limit)
                )
        except Exception:
            # Fallback: regex scan when $text index is unavailable
            docs = list(
                self._col.find(
                    {"user_id": user_id,
                     "messages.content": {"$regex": keyword, "$options": "i"}}
                ).limit(limit)
            )
        return [_doc_to_entry(doc) for doc in docs]

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
        result = self._col.delete_one({"_id": session_id})
        deleted = result.deleted_count > 0
        if deleted:
            _log.info("Session deleted", extra={"session_id": session_id})
        return deleted

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._client.close()
        _log.info("MongoHistoryBackend connection closed")
