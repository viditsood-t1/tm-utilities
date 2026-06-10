# session-history-saver

> **Track and persist user interaction history across sessions** — for AI chatbots, query tools, and any workflow requiring session continuity, auditing, or fine-tuning data collection.

---

## Features

| Feature | Detail |
|---|---|
| **Zero dependencies** | Pure Python stdlib — no third-party packages required |
| **3 storage backends** | In-memory · JSON files · SQLite |
| **Pluggable** | Bring your own backend by subclassing `BaseStorage` |
| **Rich message model** | role, content, tokens, model, latency, status, metadata |
| **Flexible API** | Direct calls · context manager · decorator |
| **Export formats** | JSON · JSONL · CSV · Markdown · plain text |
| **Env-variable config** | All settings overridable via `SHS_*` env vars |
| **Thread-safe** | All backends use locking where required |
| **Pagination + search** | Full-text search across message content |

---

## Installation

```bash
# From source
pip install .

# For development (includes pytest)
pip install -e ".[dev]"
```

---

## Quick Start

```python
from session_history_saver import SessionTracker

# SQLite backend (persists across restarts)
tracker = SessionTracker(backend="sqlite", db_path="./history.db")

# Start a session
session = tracker.start_session(user_id="alice", project_id="my-chatbot")

# Log messages
tracker.add_user_message(session.session_id, "Hello!")
tracker.add_assistant_message(
    session.session_id,
    "Hi! How can I help?",
    tokens=12, model="claude-3-sonnet", latency_ms=320.0
)

# End and persist
tracker.end_session(session.session_id)
```

---

## Backends

### In-Memory (testing / short-lived scripts)
```python
tracker = SessionTracker(backend="memory")
```
Data lives only for the process lifetime. Ideal for unit tests.

### JSON files
```python
tracker = SessionTracker(backend="json", storage_dir="./sessions")
# Each session → ./sessions/<session_id>.json
```
Human-readable, portable, no database setup needed.

### SQLite (recommended for production)
```python
tracker = SessionTracker(backend="sqlite", db_path="./history.db")
```
Efficient, searchable, WAL-mode enabled for concurrent writes.

### Custom backend
```python
from session_history_saver import BaseStorage

class MyRedisStorage(BaseStorage):
    def save_session(self, session): ...
    def load_session(self, session_id): ...
    def delete_session(self, session_id): ...
    def list_sessions(self, **kwargs): ...
    def session_exists(self, session_id): ...

tracker = SessionTracker(custom_storage=MyRedisStorage())
```

---

## Usage Patterns

### 1 — Direct API
```python
session = tracker.start_session(
    user_id="alice",
    project_id="support-bot",
    title="Billing query",
    tags=["billing", "priority"],
    metadata={"channel": "web"},
)

tracker.add_message(session.session_id, role="user", content="I was double-charged.")
tracker.add_message(
    session.session_id,
    role="assistant",
    content="I can see the duplicate charge. Let me fix that.",
    tokens=18, model="claude-3-sonnet", latency_ms=410
)

tracker.end_session(session.session_id)
```

### 2 — Context manager
```python
with tracker.track_session(user_id="bob", project_id="onboarding") as s:
    tracker.add_user_message(s.session_id, "How do I get started?")
    tracker.add_assistant_message(s.session_id, "Welcome! Let's begin with setup.")
# session is automatically ended on exit
```

### 3 — Decorator (wraps any function)
```python
@tracker.track(project_id="search-service")
def run_query(question: str) -> str:
    return llm.generate(question)   # your LLM call here

answer = run_query("What is quantum entanglement?")
# First positional str arg → user message
# Return value             → assistant message
```

---

## Message Parameters

| Parameter | Type | Description |
|---|---|---|
| `role` | `str` | `user`, `assistant`, `system`, `tool` |
| `content` | `str` | Message body |
| `tokens` | `int` | Token count (for cost tracking) |
| `model` | `str` | Model name (e.g. `claude-3-sonnet`) |
| `latency_ms` | `float` | Response time in milliseconds |
| `status` | `str` | `delivered`, `pending`, `error` |
| `metadata` | `dict` | Arbitrary key-value pairs |
| `message_id` | `str` | Override auto-generated UUID |
| `timestamp` | `datetime` | Override auto-generated UTC time |

---

## Retrieval

```python
# Get a single session
session = tracker.get_session(session_id)

# Get all messages
messages = tracker.get_messages(session_id)

# List with filters
sessions = tracker.list_sessions(
    user_id="alice",
    project_id="support-bot",
    tags=["billing"],
    limit=50,
    offset=0,
)

# Full-text search across message content
results = tracker.search("double-charged", limit=20)

# Stats — global
print(tracker.stats())
# {'total_sessions': 42, 'total_messages': 310, 'total_tokens': 18200, 'active_sessions': 1}

# Stats — single session
print(tracker.stats(session_id))
# {'message_count': 4, 'total_tokens': 56, 'duration_seconds': 12.3, ...}
```

---

## Export

```python
from session_history_saver import to_json, to_csv, to_jsonl, to_markdown, to_plain_text, save_to_file

session = tracker.get_session(session_id)

# JSON string
json_str = to_json(session)

# JSONL (batch of sessions — great for fine-tuning datasets)
jsonl_str = to_jsonl(tracker.list_sessions(project_id="my-app"))
save_to_file(jsonl_str, "./finetune_data.jsonl")

# CSV
csv_str = to_csv([session])
save_to_file(csv_str, "./export.csv")

# Markdown (human-readable audit trail)
md = to_markdown(session, include_metadata=True)
save_to_file(md, "./session_report.md")

# Plain text (one line per turn)
print(to_plain_text(session))
```

---

## Configuration

### Via constructor
```python
tracker = SessionTracker(
    backend="sqlite",           # memory | json | sqlite
    db_path="./history.db",    # SQLite path
    storage_dir="./sessions",  # JSON directory
    auto_save=True,            # persist on every add_message
    default_user_id="system",  # fallback user
    default_project_id="prod", # fallback project
)
```

### Via `SessionHistoryConfig` + environment variables
```bash
export SHS_BACKEND=sqlite
export SHS_DB_PATH=/var/data/history.db
export SHS_DEFAULT_PROJECT=my-app
export SHS_AUTO_SAVE=true
```

```python
from session_history_saver import SessionHistoryConfig, SessionTracker

cfg = SessionHistoryConfig()                  # reads env vars automatically
tracker = SessionTracker(**cfg.to_tracker_kwargs())
```

### Environment variable reference

| Variable | Default | Description |
|---|---|---|
| `SHS_BACKEND` | `sqlite` | Storage backend |
| `SHS_DB_PATH` | `./session_history.db` | SQLite DB path |
| `SHS_STORAGE_DIR` | `./session_history` | JSON file directory |
| `SHS_AUTO_SAVE` | `true` | Auto-persist on every message |
| `SHS_DEFAULT_USER` | — | Fallback user ID |
| `SHS_DEFAULT_PROJECT` | — | Fallback project ID |

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v --tb=short
```

---

## Project Structure

```
session_history_saver/
├── session_history_saver/
│   ├── __init__.py      # Public API
│   ├── models.py        # Message, Session data models
│   ├── storage.py       # InMemoryStorage, JSONStorage, SQLiteStorage
│   ├── tracker.py       # SessionTracker — main interface
│   ├── exporters.py     # to_json, to_csv, to_markdown, …
│   └── config.py        # SessionHistoryConfig
├── tests/
│   └── test_session_history.py
├── examples/
│   └── usage.py
├── pyproject.toml
└── README.md
```

---

## License

MIT
