"""
consolidated_utility.utils.models
----------------------------------
Shared Pydantic models and enums used across the package.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class BackendType(str, Enum):
    """Supported persistence backends."""
    POSTGRESQL = "postgresql"
    MONGODB    = "mongodb"


class MessageRole(str, Enum):
    USER      = "user"
    ASSISTANT = "assistant"
    SYSTEM    = "system"


class Message(BaseModel):
    """A single turn in a conversation."""
    role:      MessageRole
    content:   str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata:  Dict[str, Any] = Field(default_factory=dict)


class HistoryEntry(BaseModel):
    """Complete record for one session."""
    session_id:  str            = Field(default_factory=lambda: str(uuid4()))
    user_id:     str
    messages:    List[Message]  = Field(default_factory=list)
    created_at:  datetime       = Field(default_factory=datetime.utcnow)
    updated_at:  datetime       = Field(default_factory=datetime.utcnow)
    tags:        List[str]      = Field(default_factory=list)
    metadata:    Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class SessionReplay(BaseModel):
    """Result returned by a replay operation."""
    session_id:    str
    user_id:       str
    total_turns:   int
    messages:      List[Message]
    replayed_at:   datetime = Field(default_factory=datetime.utcnow)
    summary:       Optional[str] = None
