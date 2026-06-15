"""
SessionTracker — main public interface for session history management.
"""
from __future__ import annotations

import functools
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Generator, List, Optional, TypeVar, Union

from .models import Message, MessageStatus, Role, Session
from .storage import BaseStorage, InMemoryStorage, JSONStorage, SQLiteStorage

F = TypeVar("F", bound=Callable[..., Any])


class SessionTracker:
    """
    High-level interface for capturing and persisting interaction history.

    Quick-start::

        from session_history_saver import SessionTracker

        tracker = SessionTracker(backend="sqlite", db_path="./history.db")

        session = tracker.start_session(user_id="alice", project_id="chatbot-v2")
        tracker.add_message(session.session_id, role="user", content="Hello!")
        tracker.add_message(session.session_id, role="assistant", content="Hi there!")
        tracker.end_session(session.session_id)

    Parameters
    ----------
    backend : str
        One of ``"memory"``, ``"json"``, ``"sqlite"``.
    storage_dir : str
        Directory for JSON backend. Ignored for others.
    db_path : str
        File path for SQLite backend. Ignored for others.
    auto_save : bool
        If True (default), persist session automatically on every add_message call.
    default_project_id : str, optional
        Fallback project ID applied to every new session when not explicitly set.
    default_user_id : str, optional
        Fallback user ID applied to every new session when not explicitly set.
    custom_storage : BaseStorage, optional
        Plug in your own storage backend.
    """

    def __init__(
        self,
        backend: str = "sqlite",
        storage_dir: str = "./session_history",
        db_path: str = "./session_history.db",
        auto_save: bool = True,
        default_project_id: Optional[str] = None,
        default_user_id: Optional[str] = None,
        custom_storage: Optional[BaseStorage] = None,
        **kwargs: Any,
    ) -> None:
        self.auto_save = auto_save
        self.default_project_id = default_project_id
        self.default_user_id = default_user_id

        if custom_storage is not None:
            self._storage = custom_storage
        elif backend == "memory":
            self._storage = InMemoryStorage()
        elif backend == "json":
            self._storage = JSONStorage(storage_dir=storage_dir)
        elif backend == "sqlite":
            self._storage = SQLiteStorage(db_path=db_path)
        elif backend == "mongodb":
            from .storage import MongoDBStorage
            mongo_uri = kwargs.get("mongo_uri", "mongodb://localhost:27017")
            mongo_db = kwargs.get("mongo_db", "session_history")
            mongo_collection = kwargs.get("mongo_collection", "sessions")
            self._storage = MongoDBStorage(
                uri=mongo_uri,
                db_name=mongo_db,
                collection_name=mongo_collection,
            )
        else:
            raise ValueError(f"Unknown backend: {backend!r}. Choose 'memory', 'json', 'sqlite', or 'mongodb'.")

        self._active_sessions: Dict[str, Session] = {}

    # ── Session lifecycle ─────────────────────────────────────────────

    def start_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Session:
        """
        Create and register a new session.

        Returns the :class:`Session` object so callers can access ``session.session_id``.
        """
        session = Session(
            session_id=session_id,
            user_id=user_id or self.default_user_id,
            project_id=project_id or self.default_project_id,
            title=title,
            tags=tags or [],
            metadata=metadata or {},
        )
        self._active_sessions[session.session_id] = session
        if self.auto_save:
            self._storage.save_session(session)
        return session

    def end_session(self, session_id: str) -> Optional[Session]:
        """
        Mark a session as completed and flush it to storage.
        Removes it from the active-session cache.
        """
        session = self._get_session(session_id)
        if session is None:
            return None
        self._storage.save_session(session)
        self._active_sessions.pop(session_id, None)
        return session

    def resume_session(self, session_id: str) -> Optional[Session]:
        """
        Load an existing session back into the active cache so messages can be appended.
        """
        session = self._storage.load_session(session_id)
        if session is None:
            return None
        self._active_sessions[session_id] = session
        return session

    # ── Message management ────────────────────────────────────────────

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        message_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tokens: Optional[int] = None,
        model: Optional[str] = None,
        latency_ms: Optional[float] = None,
        status: str = MessageStatus.DELIVERED,
        timestamp: Optional[datetime] = None,
    ) -> Message:
        """
        Append a message to the session, persisting if ``auto_save=True``.

        Returns the created :class:`Message` object.
        """
        message = Message(
            role=role,
            content=content,
            message_id=message_id,
            metadata=metadata or {},
            tokens=tokens,
            model=model,
            latency_ms=latency_ms,
            status=status,
            timestamp=timestamp or datetime.now(timezone.utc),
        )

        # Update in-memory copy if session is cached
        session = self._active_sessions.get(session_id)
        if session is not None:
            session.add_message(message)
            if self.auto_save:
                self._storage.append_message(session_id, message)
        else:
            # Session not in active cache — try storage-only append
            if self.auto_save:
                self._storage.append_message(session_id, message)

        return message

    def add_user_message(self, session_id: str, content: str, **kwargs: Any) -> Message:
        """Convenience wrapper — adds a message with role='user'."""
        return self.add_message(session_id, role=Role.USER, content=content, **kwargs)

    def add_assistant_message(self, session_id: str, content: str, **kwargs: Any) -> Message:
        """Convenience wrapper — adds a message with role='assistant'."""
        return self.add_message(session_id, role=Role.ASSISTANT, content=content, **kwargs)

    def add_system_message(self, session_id: str, content: str, **kwargs: Any) -> Message:
        """Convenience wrapper — adds a message with role='system'."""
        return self.add_message(session_id, role=Role.SYSTEM, content=content, **kwargs)

    # ── Decorator / context manager ───────────────────────────────────

    @contextmanager
    def track_session(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Generator[Session, None, None]:
        """
        Context manager that automatically starts and ends a session::

            with tracker.track_session(user_id="bob") as session:
                tracker.add_user_message(session.session_id, "Hello")
                tracker.add_assistant_message(session.session_id, "Hi!")
        """
        session = self.start_session(
            user_id=user_id,
            project_id=project_id,
            title=title,
            tags=tags,
            metadata=metadata,
        )
        try:
            yield session
        finally:
            self.end_session(session.session_id)

    def track(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        extract_args: bool = False,
    ) -> Callable[[F], F]:
        """
        Decorator that wraps a function and auto-tracks its call as a session::

            @tracker.track(project_id="my-app")
            def handle_query(query: str) -> str:
                response = my_llm(query)
                return response

        The decorator captures function input/output as user/assistant messages.
        """
        def decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                title = f"{func.__module__}.{func.__qualname__}"
                meta = {"function": func.__qualname__}
                if extract_args:
                    meta["args"] = str(args)
                    meta["kwargs"] = str(kwargs)

                session = self.start_session(
                    user_id=user_id,
                    project_id=project_id,
                    title=title,
                    metadata=meta,
                )
                start = time.monotonic()
                try:
                    # Capture first positional string arg as user message
                    user_content = next(
                        (a for a in args if isinstance(a, str)), str(kwargs)
                    )
                    self.add_user_message(session.session_id, user_content)

                    result = func(*args, **kwargs)
                    latency = (time.monotonic() - start) * 1000

                    resp_content = result if isinstance(result, str) else str(result)
                    self.add_assistant_message(
                        session.session_id, resp_content, latency_ms=latency
                    )
                    return result
                except Exception as exc:
                    self.add_message(
                        session.session_id,
                        role="system",
                        content=f"ERROR: {exc}",
                        status=MessageStatus.ERROR,
                    )
                    raise
                finally:
                    self.end_session(session.session_id)
            return wrapper  # type: ignore[return-value]
        return decorator

    # ── Retrieval ─────────────────────────────────────────────────────

    def get_session(self, session_id: str) -> Optional[Session]:
        """Load a session (from cache or storage)."""
        return self._get_session(session_id)

    def get_messages(self, session_id: str) -> List[Message]:
        """Return all messages for a session."""
        session = self._get_session(session_id)
        return session.messages if session else []

    def list_sessions(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Session]:
        """List sessions with optional filters."""
        return self._storage.list_sessions(
            user_id=user_id,
            project_id=project_id,
            tags=tags,
            limit=limit,
            offset=offset,
        )

    def search(self, query: str, limit: int = 20) -> List[Session]:
        """Search sessions by message content."""
        return self._storage.search_sessions(query=query, limit=limit)

    def delete_session(self, session_id: str) -> bool:
        """Permanently delete a session."""
        self._active_sessions.pop(session_id, None)
        return self._storage.delete_session(session_id)

    def export_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Export a session as a plain dict (ready for JSON serialisation)."""
        session = self._get_session(session_id)
        return session.to_dict() if session else None

    def import_session(self, data: Dict[str, Any], overwrite: bool = False) -> Session:
        """Import a session from a dict. Raises ValueError if it already exists and overwrite=False."""
        session_id = data.get("session_id", "")
        if not overwrite and self._storage.session_exists(session_id):
            raise ValueError(f"Session {session_id!r} already exists. Pass overwrite=True to replace it.")
        session = Session.from_dict(data)
        self._storage.save_session(session)
        return session

    # ── Stats ─────────────────────────────────────────────────────────

    def stats(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Return stats for a single session or global aggregate stats.
        """
        if session_id:
            session = self._get_session(session_id)
            if not session:
                return {}
            return {
                "session_id": session.session_id,
                "message_count": session.message_count,
                "total_tokens": session.total_tokens,
                "duration_seconds": session.duration_seconds,
                "user_id": session.user_id,
                "project_id": session.project_id,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
            }
        sessions = self._storage.list_sessions(limit=10_000)
        total_msgs = sum(s.message_count for s in sessions)
        total_tokens = sum(s.total_tokens for s in sessions)
        return {
            "total_sessions": len(sessions),
            "total_messages": total_msgs,
            "total_tokens": total_tokens,
            "active_sessions": len(self._active_sessions),
        }

    # ── Private ───────────────────────────────────────────────────────

    def _get_session(self, session_id: str) -> Optional[Session]:
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]
        return self._storage.load_session(session_id)
