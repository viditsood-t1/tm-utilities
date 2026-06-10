# Consolidated Python Utility Package

A single, unified library that replaces fragmented, project-specific scripts with a
standardised, reusable, and plug-and-play toolkit.

---

## Package Structure

```
consolidated_utility/
├── consolidated_utility/
│   ├── __init__.py              # Public API surface
│   ├── config/
│   │   └── __init__.py          # Centralised settings (env / .env file)
│   ├── logging/
│   │   └── __init__.py          # Structured JSON audit logger
│   ├── utils/
│   │   ├── __init__.py
│   │   └── models.py            # Shared Pydantic models & enums
│   └── history/
│       ├── __init__.py
│       ├── base.py              # Abstract backend interface
│       ├── manager.py           # HistoryManager facade (entry-point)
│       ├── sql_backend.py       # PostgreSQL backend (SQLAlchemy)
│       └── mongo_backend.py     # MongoDB backend (pymongo)
├── tests/
│   ├── conftest.py              # Fixtures (SQLite in-memory + mongomock)
│   ├── test_models.py
│   ├── test_logging.py
│   ├── test_sql_backend.py
│   ├── test_mongo_backend.py
│   └── test_history_manager.py
├── .env.example
├── pytest.ini
└── setup.py
```

---

## Installation

```bash
# From source
pip install -e .

# With dev tools
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and fill in your connection details:

```bash
cp .env.example .env
```

---

## Quick Start

### PostgreSQL

```python
from consolidated_utility import HistoryManager
from consolidated_utility.utils.models import MessageRole, BackendType

mgr = HistoryManager(
    BackendType.POSTGRESQL,
    dsn="postgresql+psycopg2://user:pass@localhost/mydb",
)

# Create a session
session = mgr.create_session(
    user_id="user-123",
    tags=["support", "onboarding"],
)

# Add turns
mgr.add_message(session.session_id, MessageRole.USER,      "Hello!")
mgr.add_message(session.session_id, MessageRole.ASSISTANT, "Hi! How can I help?")

# Fetch history
history = mgr.get_user_history("user-123", limit=10)

# Replay a session (returns structured SessionReplay object)
replay = mgr.replay(session.session_id)
print(f"Replaying {replay.total_turns} turns")

mgr.close()
```

### MongoDB

```python
from consolidated_utility import HistoryManager
from consolidated_utility.utils.models import BackendType

mgr = HistoryManager(
    BackendType.MONGODB,
    uri="mongodb://localhost:27017",
    db_name="mydb",
)

# Same API — backend is transparent
session = mgr.create_session("user-456")
mgr.add_message(session.session_id, MessageRole.USER, "What is MLOps?")
```

### Context Manager (auto-close)

```python
with HistoryManager(BackendType.POSTGRESQL, dsn="...") as mgr:
    session = mgr.create_session("user-789")
    # resources released automatically on exit
```

### Auto-detect backend from DSN string

```python
mgr = HistoryManager("mongodb://localhost:27017/mydb")   # → Mongo
mgr = HistoryManager("postgresql+psycopg2://u:p@h/db")  # → SQL
```

---

## API Reference

### `HistoryManager`

| Method | Description |
|--------|-------------|
| `create_session(user_id, messages?, tags?, metadata?)` | Create & persist a new session |
| `add_message(session_id, role, content, metadata?)` | Append a single message turn |
| `save_session(entry)` | Upsert a fully-formed `HistoryEntry` |
| `get_session(session_id)` | Fetch one session by ID |
| `get_user_history(user_id, limit, offset, start_date, end_date, tags)` | Paginated history with filters |
| `search(user_id, keyword, limit)` | Full-text search across message content |
| `replay(session_id)` | Return a `SessionReplay` object for replaying a session |
| `delete_session(session_id)` | Hard-delete a session |
| `close()` | Release backend resources |

### Models

| Model | Fields |
|-------|--------|
| `HistoryEntry` | `session_id`, `user_id`, `messages`, `created_at`, `updated_at`, `tags`, `metadata` |
| `Message` | `role` (user/assistant/system), `content`, `timestamp`, `metadata` |
| `SessionReplay` | `session_id`, `user_id`, `total_turns`, `messages`, `replayed_at`, `summary` |

---

## Configuration

All settings are read from environment variables (or a `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `utility_db` | Database name |
| `POSTGRES_USER` | `postgres` | Username |
| `POSTGRES_PASSWORD` | `postgres` | Password |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection URI |
| `MONGO_DB` | `utility_db` | Database name |
| `MONGO_COLLECTION` | `sessions` | Collection name |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DEFAULT_PAGE_SIZE` | `20` | Default pagination size |

---

## Running Tests

Tests use **SQLite in-memory** (no PostgreSQL required) and **mongomock** (no MongoDB required):

```bash
pytest                  # all 90 tests
pytest -v               # verbose
pytest tests/test_sql_backend.py   # SQL only
pytest tests/test_mongo_backend.py # Mongo only
```

---

## Logging Output

Every operation emits a structured JSON log line:

```json
{
  "timestamp": "2026-06-10T08:00:00.000Z",
  "level": "INFO",
  "logger": "history.manager",
  "message": "Replaying session",
  "session_id": "abc-123"
}
```

Set `LOG_LEVEL=DEBUG` to see every SQL statement or MongoDB operation.

---

## Extending the Package

To add a new backend (e.g. Redis, DynamoDB), subclass `BaseHistoryBackend` and implement all abstract methods:

```python
from consolidated_utility.history.base import BaseHistoryBackend

class RedisHistoryBackend(BaseHistoryBackend):
    def save_session(self, entry): ...
    def get_session(self, session_id): ...
    # ... implement remaining abstract methods
```

Then pass an instance directly to `HistoryManager`:

```python
mgr = HistoryManager(backend=RedisHistoryBackend(...))
```
