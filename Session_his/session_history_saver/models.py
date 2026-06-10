"""
Data models for session history tracking.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field, field_validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False


class Role(str, Enum):
    """Message role in a conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class MessageStatus(str, Enum):
    """Status of a message."""
    PENDING = "pending"
    DELIVERED = "delivered"
    ERROR = "error"


class Message:
    """Represents a single message in a session."""

    def __init__(
        self,
        role: str,
        content: str,
        message_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = MessageStatus.DELIVERED,
        tokens: Optional[int] = None,
        model: Optional[str] = None,
        latency_ms: Optional[float] = None,
    ):
        self.message_id: str = message_id or str(uuid.uuid4())
        self.role: str = role
        self.content: str = content
        self.timestamp: datetime = timestamp or datetime.now(timezone.utc)
        self.metadata: Dict[str, Any] = metadata or {}
        self.status: str = status
        self.tokens: Optional[int] = tokens
        self.model: Optional[str] = model
        self.latency_ms: Optional[float] = latency_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "status": self.status,
            "tokens": self.tokens,
            "model": self.model,
            "latency_ms": self.latency_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        return cls(
            role=data["role"],
            content=data["content"],
            message_id=data.get("message_id"),
            timestamp=ts,
            metadata=data.get("metadata", {}),
            status=data.get("status", MessageStatus.DELIVERED),
            tokens=data.get("tokens"),
            model=data.get("model"),
            latency_ms=data.get("latency_ms"),
        )

    def __repr__(self) -> str:
        return f"Message(role={self.role!r}, content={self.content[:50]!r}...)"


class Session:
    """Represents a complete conversation session."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.session_id: str = session_id or str(uuid.uuid4())
        self.user_id: Optional[str] = user_id
        self.project_id: Optional[str] = project_id
        self.tags: List[str] = tags or []
        self.metadata: Dict[str, Any] = metadata or {}
        self.title: Optional[str] = title
        self.created_at: datetime = created_at or datetime.now(timezone.utc)
        self.updated_at: datetime = updated_at or datetime.now(timezone.utc)
        self.messages: List[Message] = []

    def add_message(self, message: Message) -> None:
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def total_tokens(self) -> int:
        return sum(m.tokens or 0 for m in self.messages)

    @property
    def duration_seconds(self) -> Optional[float]:
        if len(self.messages) < 2:
            return None
        return (self.messages[-1].timestamp - self.messages[0].timestamp).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "tags": self.tags,
            "metadata": self.metadata,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
            "duration_seconds": self.duration_seconds,
            "messages": [m.to_dict() for m in self.messages],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        created = data.get("created_at")
        updated = data.get("updated_at")
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        if isinstance(updated, str):
            updated = datetime.fromisoformat(updated)

        session = cls(
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
            project_id=data.get("project_id"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            title=data.get("title"),
            created_at=created,
            updated_at=updated,
        )
        for msg_data in data.get("messages", []):
            session.messages.append(Message.from_dict(msg_data))
        return session

    def __repr__(self) -> str:
        return (
            f"Session(id={self.session_id!r}, "
            f"messages={self.message_count}, "
            f"user={self.user_id!r})"
        )
