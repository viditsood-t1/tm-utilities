"""
Configuration helpers for the session history saver library.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SessionHistoryConfig:
    """
    Centralised configuration. All values can also be set via environment variables.

    Environment variables (take precedence over dataclass defaults):

    General:
        SHS_BACKEND          — memory | json | sqlite | mongodb
        SHS_AUTO_SAVE        — true | false
        SHS_DEFAULT_USER     — default user id
        SHS_DEFAULT_PROJECT  — default project id

    SQLite:
        SHS_DB_PATH          — path for sqlite backend  (default: ./session_history.db)

    JSON:
        SHS_STORAGE_DIR      — path for json backend    (default: ./session_history)

    MongoDB:
        SHS_MONGO_URI        — connection URI            (default: mongodb://localhost:27017)
        SHS_MONGO_DB         — database name             (default: session_history)
        SHS_MONGO_COLLECTION — collection name           (default: sessions)
    """
    backend: str = "sqlite"

    # SQLite
    db_path: str = "./session_history.db"

    # JSON
    storage_dir: str = "./session_history"

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "session_history"
    mongo_collection: str = "sessions"

    # Common
    auto_save: bool = True
    default_user_id: Optional[str] = None
    default_project_id: Optional[str] = None

    def __post_init__(self) -> None:
        # General
        self.backend        = os.getenv("SHS_BACKEND",        self.backend)
        self.auto_save      = os.getenv("SHS_AUTO_SAVE",      str(self.auto_save)).lower() not in ("false", "0", "no")
        self.default_user_id    = os.getenv("SHS_DEFAULT_USER",    self.default_user_id)
        self.default_project_id = os.getenv("SHS_DEFAULT_PROJECT", self.default_project_id)

        # SQLite
        self.db_path        = os.getenv("SHS_DB_PATH",        self.db_path)

        # JSON
        self.storage_dir    = os.getenv("SHS_STORAGE_DIR",    self.storage_dir)

        # MongoDB
        self.mongo_uri        = os.getenv("SHS_MONGO_URI",        self.mongo_uri)
        self.mongo_db         = os.getenv("SHS_MONGO_DB",         self.mongo_db)
        self.mongo_collection = os.getenv("SHS_MONGO_COLLECTION", self.mongo_collection)

    def to_tracker_kwargs(self) -> dict:
        """Return kwargs ready to unpack into SessionTracker(...)."""
        return {
            "backend":            self.backend,
            "db_path":            self.db_path,
            "storage_dir":        self.storage_dir,
            "auto_save":          self.auto_save,
            "default_user_id":    self.default_user_id,
            "default_project_id": self.default_project_id,
            # MongoDB-specific (ignored by other backends)
            "mongo_uri":          self.mongo_uri,
            "mongo_db":           self.mongo_db,
            "mongo_collection":   self.mongo_collection,
        }
