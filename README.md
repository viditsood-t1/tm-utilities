# tm-utility

A Python utility library providing reusable service wrappers for MongoDB, SQL (ODBC), logging, and vector store operations.

---

## Installation

```bash
pip install tm-utility
```

---

## Modules

### `logger`

Structured file + console logger with IST timezone and daily log rotation.

```python
from tm_utility.loggerService import logger, logger_title, LOG_DIR, DEBUG

logger.info("Application started")
logger.debug("Debug details")

logger_title("My Section")  # prints a formatted section banner
```

Logs are saved under `./logs/<Mon_YYYY>/<DD-MM-YYYY>.log` by default.

---

### `mongoService`

MongoDB connection wrapper built on `pymongo`.

```python
from tm_utility.mongoService import MongoService

# Uses MONGODB_URI and MONGODB_DB env vars by default
mongo = MongoService()

col = mongo.collection("my_collection")
col.insert_one({"key": "value"})

mongo.close()
```

**Environment variables:**

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection URI |
| `MONGODB_DB` | — | Database name |

#### Rulebook

Store and retrieve LLM instruction rules.

```python
# Save a rulebook (string or dict or list)
mongo.insert_rulebook("Always respond in formal English.", rulebook_id="default")
mongo.insert_rulebook({"rulebook": "Be concise.", "version": 1}, rulebook_id="v2")

# Fetch rulebook documents
docs = mongo.get_rulebook(rulebook_id="default")

# Get a ready-to-use prompt string
prompt = mongo.rulebook_prompt(rulebook_id="default")
# → "Incorporate the following rules into your reasoning:\nAlways respond in formal English."
```

#### Session History

Save, retrieve, append, search, and delete conversation history per user.

```python
# Save a new session (creates session_id automatically)
result = mongo.save_user_history(
    user_id="user_123",
    messages=[
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help?"},
    ],
    title="First chat",
    tags=["onboarding"],
)

# Append messages to an existing session
mongo.append_user_history(
    user_id="user_123",
    session_id=result["session_id"],
    messages={"role": "user", "content": "Follow-up question"},
)

# Fetch one session
session = mongo.get_user_history_session(user_id="user_123", session_id="<session_id>")

# Fetch all sessions for a user (newest first)
sessions = mongo.fetch_user_history(user_id="user_123", limit=20, offset=0)

# Search message content
results = mongo.search_user_history(user_id="user_123", query="refund policy")

# Delete a session
mongo.delete_user_history(user_id="user_123", session_id="<session_id>")
```

---

### `sqlService`

Generic ODBC SQL service wrapper using `pyodbc`.

```python
from tm_utility.sqlService import SQLService

# Via connection string
sql = SQLService(connection_string="DSN=mydsn;UID=user;PWD=pass")

# Or via individual params
sql = SQLService(driver="ODBC Driver 17 for SQL Server", server="localhost", database="mydb", uid="user", pwd="pass")

rows = sql.query("SELECT * FROM my_table WHERE id = ?", params=[1])
sql.close()
```

**Environment variable:**

| Variable | Description |
|---|---|
| `ODBC_CONNECTION_STRING` | Full ODBC connection string |

#### Rulebook

```python
# Save a rulebook
sql.insert_rulebook("Always respond in formal English.", rulebook_id="default")
sql.insert_rulebook({"rulebook": "Be concise."}, rulebook_id="v2")

# Fetch rulebook rows
docs = sql.get_rulebook(rulebook_id="default")

# Get a ready-to-use prompt string
prompt = sql.rulebook_prompt(rulebook_id="default")
```

#### Session History

```python
# Save a session
sql.save_user_history(
    user_id="user_123",
    messages=[
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ],
    title="First chat",
)

# Append to an existing session
sql.append_user_history(
    user_id="user_123",
    session_id="<session_id>",
    messages={"role": "user", "content": "Another message"},
)

# Fetch one session
session = sql.get_user_history_session(user_id="user_123", session_id="<session_id>")

# Fetch all sessions for a user
sessions = sql.fetch_user_history(user_id="user_123", limit=20, offset=0)

# Search message content
results = sql.search_user_history(user_id="user_123", query="refund policy")

# Delete a session
sql.delete_user_history(user_id="user_123", session_id="<session_id>")
```

---

### `vectorstore`

Ingest documents (PDF, DOCX) using ChromaDB embeddings.
```python
from tm_utility.vectorstore import ingest_document, retrieve

# Ingest a single file or a folder
ingest_document(
    file_path="./docs/manual.pdf",
    metadata=False, #[Optional] default - True
    embedding_mode="chunk",   # "chunk" | "page" | "file"
    chroma_path="./chroma_db",
    chunk_size=1000, #[Optional] default = 1000
    chunk_overlap=200, #[Optional] default = 200
)
```
Retrieve documents (PDF, DOCX) using ChromaDB embeddings.
```python
from tm_utility.vectorstore import retrieve

# Retrieve relevant chunks
results = retrieve(
    query="What is the refund policy?",
    chroma_path="./chroma_db", #[Optional] default = ./chroma_db
    top_k=5, #[Optional] default = 5
)

for r in results:
    print(r["score"], r["content"])
```

**Supported file types:** `.pdf`, `.docx`

**Embedding modes:**

| Mode | Description |
|---|---|
| `chunk` | Splits document into overlapping text chunks |
| `page` | One embedding per page |
| `file` | Single embedding for the entire file |

---

## Environment Variables Summary

| Variable | Module | Description |
|---|---|---|
| `MONGODB_URI` | mongoService | MongoDB connection URI |
| `MONGODB_DB` | mongoService | MongoDB database name |
| `ODBC_CONNECTION_STRING` | sqlService | ODBC connection string |

---
## Authors
Vidit Sood, Rahul Sharma, Anikait Kapoor

---
## License
MIT © 2026 Vidit Sood, Rahul Sharma, Anikait Kapoor
