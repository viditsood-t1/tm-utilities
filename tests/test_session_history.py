"""
Tests for session_history_saver.
Run with:  python -m pytest tests/ -v
"""
import json
import os
import tempfile
import time
import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from session_history_saver import (
    InMemoryStorage,
    JSONStorage,
    Message,
    MessageStatus,
    Role,
    Session,
    SessionHistoryConfig,
    SessionTracker,
    SQLiteStorage,
    to_csv,
    to_json,
    to_jsonl,
    to_markdown,
    to_plain_text,
)


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def mem_tracker():
    return SessionTracker(backend="memory")


@pytest.fixture
def tmp_sqlite(tmp_path):
    return SessionTracker(backend="sqlite", db_path=str(tmp_path / "test.db"))


@pytest.fixture
def tmp_json(tmp_path):
    return SessionTracker(backend="json", storage_dir=str(tmp_path / "sessions"))


@pytest.fixture
def sample_session(mem_tracker):
    session = mem_tracker.start_session(user_id="alice", project_id="proj-1", title="Test Session")
    mem_tracker.add_user_message(session.session_id, "Hello!")
    mem_tracker.add_assistant_message(session.session_id, "Hi there!", tokens=10, model="claude-3")
    return session


# ─────────────────────────────────────────────
# Model tests
# ─────────────────────────────────────────────

class TestMessage:
    def test_defaults(self):
        m = Message(role="user", content="hi")
        assert m.role == "user"
        assert m.content == "hi"
        assert m.message_id is not None
        assert m.timestamp is not None

    def test_roundtrip(self):
        m = Message(role="assistant", content="hello", tokens=5, model="gpt-4", latency_ms=123.4)
        d = m.to_dict()
        m2 = Message.from_dict(d)
        assert m2.role == m.role
        assert m2.content == m.content
        assert m2.tokens == m.tokens
        assert m2.model == m.model
        assert abs(m2.latency_ms - m.latency_ms) < 0.01


class TestSession:
    def test_defaults(self):
        s = Session(user_id="bob")
        assert s.user_id == "bob"
        assert s.message_count == 0
        assert s.total_tokens == 0

    def test_add_message(self):
        s = Session()
        s.add_message(Message(role="user", content="hey"))
        assert s.message_count == 1

    def test_total_tokens(self):
        s = Session()
        s.add_message(Message(role="user", content="hey", tokens=5))
        s.add_message(Message(role="assistant", content="hello", tokens=10))
        assert s.total_tokens == 15

    def test_roundtrip(self):
        s = Session(user_id="carol", project_id="p1", tags=["beta"])
        s.add_message(Message(role="user", content="q"))
        s.add_message(Message(role="assistant", content="a"))
        d = s.to_dict()
        s2 = Session.from_dict(d)
        assert s2.session_id == s.session_id
        assert s2.user_id == s.user_id
        assert s2.tags == s.tags
        assert s2.message_count == s.message_count


# ─────────────────────────────────────────────
# Storage backend tests (parametrised)
# ─────────────────────────────────────────────

def _run_storage_suite(storage: any):
    """Common assertions run against every backend."""
    s = Session(user_id="u1", project_id="p1", tags=["x"])
    s.add_message(Message(role="user", content="ping"))
    

    # Save / load
    storage.save_session(s)
    loaded = storage.load_session(s.session_id)
    assert loaded is not None
    assert loaded.session_id == s.session_id
    assert loaded.message_count == 1
    assert loaded.messages[0].content == "ping"

    # Exists
    assert storage.session_exists(s.session_id)
    assert not storage.session_exists("nonexistent-id")

    # Append message
    m2 = Message(role="assistant", content="pong")
    storage.append_message(s.session_id, m2)
    loaded2 = storage.load_session(s.session_id)
    assert loaded2.message_count == 2

    # List
    sessions = storage.list_sessions()
    assert any(x.session_id == s.session_id for x in sessions)

    # Filter by user_id
    filtered = storage.list_sessions(user_id="u1")
    assert all(x.user_id == "u1" for x in filtered)

    # Delete
    assert storage.delete_session(s.session_id)
    assert not storage.session_exists(s.session_id)


class TestInMemoryStorage:
    def test_suite(self):
        _run_storage_suite(InMemoryStorage())

    def test_clear(self):
        st = InMemoryStorage()
        s = Session()
        st.save_session(s)
        st.clear()
        assert not st.session_exists(s.session_id)


class TestJSONStorage:
    def test_suite(self, tmp_path):
        _run_storage_suite(JSONStorage(storage_dir=str(tmp_path)))

    def test_file_created(self, tmp_path):
        st = JSONStorage(storage_dir=str(tmp_path))
        s = Session()
        st.save_session(s)
        assert (tmp_path / f"{s.session_id}.json").exists()


class TestSQLiteStorage:
    def test_suite(self, tmp_path):
        _run_storage_suite(SQLiteStorage(db_path=str(tmp_path / "t.db")))

    def test_search(self, tmp_path):
        st = SQLiteStorage(db_path=str(tmp_path / "search.db"))
        s = Session()
        s.add_message(Message(role="user", content="the quick brown fox"))
        st.save_session(s)
        results = st.search_sessions("brown fox")
        assert any(x.session_id == s.session_id for x in results)


# ─────────────────────────────────────────────
# SessionTracker tests
# ─────────────────────────────────────────────

class TestSessionTracker:
    def test_start_and_end(self, mem_tracker):
        session = mem_tracker.start_session(user_id="u1")
        assert session.session_id in mem_tracker._active_sessions
        mem_tracker.end_session(session.session_id)
        assert session.session_id not in mem_tracker._active_sessions

    def test_add_messages(self, mem_tracker):
        s = mem_tracker.start_session()
        mem_tracker.add_user_message(s.session_id, "hello")
        mem_tracker.add_assistant_message(s.session_id, "world")
        msgs = mem_tracker.get_messages(s.session_id)
        assert len(msgs) == 2
        assert msgs[0].role == Role.USER
        assert msgs[1].role == Role.ASSISTANT

    def test_resume_session(self, tmp_sqlite):
        s = tmp_sqlite.start_session(user_id="dave")
        tmp_sqlite.add_user_message(s.session_id, "hi")
        tmp_sqlite.end_session(s.session_id)

        s2 = tmp_sqlite.resume_session(s.session_id)
        assert s2 is not None
        tmp_sqlite.add_assistant_message(s2.session_id, "welcome back")
        msgs = tmp_sqlite.get_messages(s2.session_id)
        assert len(msgs) == 2

    def test_context_manager(self, mem_tracker):
        with mem_tracker.track_session(user_id="ctx") as s:
            mem_tracker.add_user_message(s.session_id, "in context")
        assert s.session_id not in mem_tracker._active_sessions

    def test_decorator(self, mem_tracker):
        @mem_tracker.track(project_id="deco-test")
        def my_fn(query: str) -> str:
            return f"answer to: {query}"

        result = my_fn("what is 2+2?")
        assert result == "answer to: what is 2+2?"

        sessions = mem_tracker.list_sessions(project_id="deco-test")
        assert len(sessions) >= 1
        assert sessions[0].message_count == 2

    def test_stats_global(self, sample_session, mem_tracker):
        stats = mem_tracker.stats()
        assert stats["total_sessions"] >= 1
        assert stats["total_messages"] >= 2

    def test_stats_single(self, sample_session, mem_tracker):
        stats = mem_tracker.stats(sample_session.session_id)
        assert stats["message_count"] == 2
        assert stats["total_tokens"] == 10

    def test_export_import(self, mem_tracker):
        s = mem_tracker.start_session(user_id="exp")
        mem_tracker.add_user_message(s.session_id, "export me")
        data = mem_tracker.export_session(s.session_id)
        assert data is not None

        tracker2 = SessionTracker(backend="memory")
        s2 = tracker2.import_session(data)
        assert s2.session_id == s.session_id
        assert s2.message_count == 1

    def test_delete(self, mem_tracker):
        s = mem_tracker.start_session()
        mem_tracker.end_session(s.session_id)
        assert mem_tracker.delete_session(s.session_id)
        assert mem_tracker.get_session(s.session_id) is None

    def test_search(self, tmp_sqlite):
        s = tmp_sqlite.start_session()
        tmp_sqlite.add_user_message(s.session_id, "needle in a haystack")
        tmp_sqlite.end_session(s.session_id)
        results = tmp_sqlite.search("needle")
        assert any(x.session_id == s.session_id for x in results)

    def test_pagination(self, mem_tracker):
        for i in range(5):
            s = mem_tracker.start_session(project_id="page-test")
            mem_tracker.end_session(s.session_id)
        page1 = mem_tracker.list_sessions(project_id="page-test", limit=3, offset=0)
        page2 = mem_tracker.list_sessions(project_id="page-test", limit=3, offset=3)
        assert len(page1) == 3
        ids1 = {s.session_id for s in page1}
        ids2 = {s.session_id for s in page2}
        assert ids1.isdisjoint(ids2)


# ─────────────────────────────────────────────
# Exporter tests
# ─────────────────────────────────────────────

class TestExporters:
    def test_to_json(self, sample_session):
        output = to_json(sample_session)
        data = json.loads(output)
        assert data["session_id"] == sample_session.session_id
        assert len(data["messages"]) == 2

    def test_to_jsonl(self, sample_session):
        lines = to_jsonl([sample_session]).split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert "session_id" in data

    def test_to_csv(self, sample_session):
        output = to_csv([sample_session])
        assert "session_id" in output
        assert "Hello!" in output

    def test_to_markdown(self, sample_session):
        md = to_markdown(sample_session)
        assert "# Test Session" in md
        assert "Hello!" in md
        assert "Hi there!" in md

    def test_to_plain_text(self, sample_session):
        text = to_plain_text(sample_session)
        assert "[USER]:" in text
        assert "[ASSISTANT]:" in text


# ─────────────────────────────────────────────
# Config tests
# ─────────────────────────────────────────────

class TestConfig:
    def test_defaults(self):
        cfg = SessionHistoryConfig()
        assert cfg.backend == "sqlite"
        assert cfg.auto_save is True

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("SHS_BACKEND", "memory")
        monkeypatch.setenv("SHS_AUTO_SAVE", "false")
        monkeypatch.setenv("SHS_DEFAULT_USER", "env-user")
        cfg = SessionHistoryConfig()
        assert cfg.backend == "memory"
        assert cfg.auto_save is False
        assert cfg.default_user_id == "env-user"

    def test_to_tracker_kwargs(self):
        cfg = SessionHistoryConfig(backend="memory")
        kwargs = cfg.to_tracker_kwargs()
        tracker = SessionTracker(**kwargs)
        assert isinstance(tracker, SessionTracker)
