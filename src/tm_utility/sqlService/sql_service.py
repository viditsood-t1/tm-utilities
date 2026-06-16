import os
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union

try:
    import pyodbc
except ImportError as exc:
    raise ImportError(
        "pyodbc is required for tm_sqlService.SQLService. Install it with `pip install pyodbc`."
    ) from exc

DEFAULT_DB_ENV = "ODBC_CONNECTION_STRING"
DEFAULT_AUTOCOMMIT = False
DEFAULT_RULEBOOK_TABLE = "rulebook"
DEFAULT_RULEBOOK_ID = "default"
DEFAULT_HISTORY_TABLE = "user_history"
RULEBOOK_ID_COLUMN = "id"
RULEBOOK_CONTENT_COLUMN = "rulebook"

Params = Union[Sequence[Any], Dict[str, Any]]


def _row_to_dict(cursor: "pyodbc.Cursor", row: "pyodbc.Row") -> Dict[str, Any]:
    if row is None:
        return {}

    columns = [column[0] for column in cursor.description or []]
    return dict(zip(columns, row))


def _params_tuple(params: Optional[Params]) -> Sequence[Any]:
    if params is None:
        return []
    if isinstance(params, dict):
        return tuple(params.values())
    if isinstance(params, (list, tuple)):
        return params
    return (params,)


class SQLService:
    """Generic ODBC SQL service wrapper using pyodbc."""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        driver: Optional[str] = None,
        server: Optional[str] = None,
        database: Optional[str] = None,
        uid: Optional[str] = None,
        pwd: Optional[str] = None,
        dsn: Optional[str] = None,
        autocommit: bool = DEFAULT_AUTOCOMMIT,
        timeout: int = 0,
        connect: bool = True,
        **kwargs: Any,
    ):
        self._connection_string = connection_string or os.getenv(DEFAULT_DB_ENV)
        self._driver = driver
        self._server = server
        self._database = database
        self._uid = uid
        self._pwd = pwd
        self._dsn = dsn
        self._autocommit = autocommit
        self._timeout = timeout
        self._kwargs = kwargs
        self._connection: Optional["pyodbc.Connection"] = None

        if connect:
            self.connect()

    def _build_connection_string(self) -> str:
        if self._connection_string:
            return self._connection_string.strip()

        parts = []
        if self._dsn:
            parts.append(f"DSN={self._dsn}")
        if self._driver:
            parts.append(f"DRIVER={{{self._driver}}}")
        if self._server:
            parts.append(f"SERVER={self._server}")
        if self._database:
            parts.append(f"DATABASE={self._database}")
        if self._uid:
            parts.append(f"UID={self._uid}")
        if self._pwd:
            parts.append(f"PWD={self._pwd}")

        if not parts:
            raise ValueError(
                "A connection string or at least one ODBC parameter is required."
            )

        return ";".join(parts)

    def connect(self) -> "pyodbc.Connection":
        """Open the ODBC connection."""
        if self._connection is not None:
            return self._connection

        connection_string = self._build_connection_string()
        self._connection = pyodbc.connect(
            connection_string,
            autocommit=self._autocommit,
            timeout=self._timeout,
            **self._kwargs,
        )
        return self._connection

    def close(self) -> None:
        """Close the ODBC connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @property
    def connection(self) -> "pyodbc.Connection":
        if self._connection is None:
            return self.connect()
        return self._connection

    @contextmanager
    def transaction(self) -> Iterator["pyodbc.Connection"]:
        """Begin a transaction, committing on success and rolling back on error."""
        connection = self.connection
        if connection.autocommit:
            yield connection
            return

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def execute(self, sql: str, params: Optional[Params] = None) -> "pyodbc.Cursor":
        """Execute a SQL statement and return the cursor."""
        cursor = self.connection.cursor()
        cursor.execute(sql, _params_tuple(params))
        return cursor

    def executemany(
        self,
        sql: str,
        seq_of_params: Iterable[Params],
    ) -> "pyodbc.Cursor":
        """Execute a SQL statement for multiple parameter sets."""
        cursor = self.connection.cursor()
        cursor.executemany(
            sql,
            [tuple(p.values()) if isinstance(p, dict) else tuple(p) for p in seq_of_params],
        )
        return cursor

    def execute_script(self, script: str) -> "pyodbc.Cursor":
        """Execute a SQL script containing one or more statements."""
        cursor = self.connection.cursor()
        statements = [statement.strip() for statement in script.split(";") if statement.strip()]
        for statement in statements:
            cursor.execute(statement)
        return cursor

    def fetchone(
        self,
        sql: str,
        params: Optional[Params] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single row from a query."""
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        result = _row_to_dict(cursor, row) if row is not None else None
        cursor.close()
        return result

    def fetchall(
        self,
        sql: str,
        params: Optional[Params] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all rows from a query."""
        cursor = self.execute(sql, params)
        rows = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        cursor.close()
        return rows

    def fetchmany(
        self,
        sql: str,
        size: int,
        params: Optional[Params] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch a limited number of rows from a query."""
        cursor = self.execute(sql, params)
        rows = [_row_to_dict(cursor, row) for row in cursor.fetchmany(size)]
        cursor.close()
        return rows

    def query(self, sql: str, params: Optional[Params] = None) -> List[Dict[str, Any]]:
        """Run a query and return all rows as dictionaries."""
        return self.fetchall(sql, params)

    def scalar(self, sql: str, params: Optional[Params] = None) -> Any:
        """Run a query and return the first column of the first row."""
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        result = None
        if row is not None:
            result = row[0]
        cursor.close()
        return result

    def _build_insert_sql(
        self,
        table_name: str,
        values: Dict[str, Any],
    ) -> Tuple[str, Tuple[Any, ...]]:
        columns = ", ".join(values.keys())
        placeholders = ", ".join("?" for _ in values)
        return f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})", tuple(values.values())

    def insert_one(self, table_name: str, values: Dict[str, Any]) -> Any:
        """Insert a single row."""
        sql, params = self._build_insert_sql(table_name, values)
        cursor = self.execute(sql, params)
        inserted_id = getattr(cursor, "lastrowid", None)
        cursor.close()
        if not self.connection.autocommit:
            self.connection.commit()
        return inserted_id

    def insert_many(self, table_name: str, rows: Iterable[Dict[str, Any]]) -> int:
        """Insert multiple rows."""
        rows_list = list(rows)
        if not rows_list:
            return 0

        columns = ", ".join(rows_list[0].keys())
        placeholders = ", ".join("?" for _ in rows_list[0])
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        params = [tuple(row.values()) for row in rows_list]

        cursor = self.connection.cursor()
        cursor.executemany(sql, params)
        count = cursor.rowcount
        cursor.close()
        if not self.connection.autocommit:
            self.connection.commit()
        return count

    def update(
        self,
        table_name: str,
        values: Dict[str, Any],
        where_clause: str,
        params: Optional[Params] = None,
    ) -> int:
        """Update rows matching the WHERE clause."""
        if not values:
            raise ValueError("Update values cannot be empty.")

        assignments = ", ".join(f"{key} = ?" for key in values)
        sql = f"UPDATE {table_name} SET {assignments} WHERE {where_clause}"
        combined_params = tuple(values.values()) + _params_tuple(params)

        cursor = self.execute(sql, combined_params)
        count = cursor.rowcount
        cursor.close()
        if not self.connection.autocommit:
            self.connection.commit()
        return count

    def delete(
        self,
        table_name: str,
        where_clause: str,
        params: Optional[Params] = None,
    ) -> int:
        """Delete rows matching the WHERE clause."""
        sql = f"DELETE FROM {table_name} WHERE {where_clause}"
        cursor = self.execute(sql, params)
        count = cursor.rowcount
        cursor.close()
        if not self.connection.autocommit:
            self.connection.commit()
        return count

    def count(
        self,
        table_name: str,
        where_clause: Optional[str] = None,
        params: Optional[Params] = None,
    ) -> int:
        """Return the number of rows in a table, optionally filtered by WHERE."""
        sql = f"SELECT COUNT(*) FROM {table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        return int(self.scalar(sql, params) or 0)

    def table_exists(self, table_name: str) -> bool:
        """Return True if the named table exists."""
        cursor = self.connection.cursor()
        try:
            cursor.tables(table=table_name)
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def get_columns(self, table_name: str) -> List[str]:
        """Return a list of column names for the given table."""
        cursor = self.connection.cursor()
        try:
            cursor.columns(table=table_name)
            columns: List[str] = []
            for row in cursor.fetchall():
                if hasattr(row, "column_name"):
                    columns.append(row.column_name)
                elif len(row) >= 4:
                    columns.append(row[3])
            return columns
        finally:
            cursor.close()

    @staticmethod
    def _require_user_id(user_id: str) -> None:
        if not user_id:
            raise ValueError("user_id is required.")

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _validate_table_name(table_name: str) -> str:
        if not table_name:
            raise ValueError("table_name is required.")

        parts = table_name.split(".")
        if not all(part.replace("_", "").isalnum() for part in parts):
            raise ValueError("table_name can only contain letters, numbers, underscores, and dots.")
        return table_name

    @staticmethod
    def _normalize_history_messages(
        messages: Union[str, Dict[str, Any], List[Union[str, Dict[str, Any]]]],
    ) -> List[Dict[str, Any]]:
        if isinstance(messages, (str, dict)):
            messages = [messages]

        normalized = []
        for message in messages:
            if isinstance(message, str):
                message = {"role": "user", "content": message}
            elif isinstance(message, dict):
                message = dict(message)
            else:
                raise TypeError("messages must contain strings or dictionaries.")

            message.setdefault("role", "user")
            message.setdefault("content", "")
            message.setdefault("timestamp", SQLService._utc_now())
            message.setdefault("metadata", {})
            normalized.append(message)

        return normalized

    @staticmethod
    def _decode_history_row(row: Dict[str, Any]) -> Dict[str, Any]:
        decoded = dict(row)
        decoded["messages"] = json.loads(decoded.get("messages") or "[]")
        decoded["tags"] = json.loads(decoded.get("tags") or "[]")
        decoded["metadata"] = json.loads(decoded.get("metadata") or "{}")
        return decoded

    def _ensure_history_table(self, table_name: str = DEFAULT_HISTORY_TABLE) -> None:
        """Create the default user history table when it does not exist."""
        table_name = self._validate_table_name(table_name)
        if self.table_exists(table_name):
            return

        cursor = self.execute(
            f"""
            CREATE TABLE {table_name} (
                session_id VARCHAR(255) PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                title VARCHAR(255),
                messages TEXT,
                tags TEXT,
                metadata TEXT,
                created_at VARCHAR(64) NOT NULL,
                updated_at VARCHAR(64) NOT NULL
            )
            """
        )
        cursor.close()
        if not self.connection.autocommit:
            self.connection.commit()

    def save_user_history(
        self,
        user_id: str,
        messages: Union[str, Dict[str, Any], List[Union[str, Dict[str, Any]]]],
        session_id: Optional[str] = None,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        table_name: str = DEFAULT_HISTORY_TABLE,
    ) -> Dict[str, Any]:
        """Create or replace one user history session."""
        self._require_user_id(user_id)
        table_name = self._validate_table_name(table_name)
        self._ensure_history_table(table_name)

        session_id = session_id or str(uuid.uuid4())
        now = self._utc_now()
        existing = self.fetchone(
            f"SELECT created_at FROM {table_name} WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        )
        created_at = existing["created_at"] if existing else now

        row = {
            "session_id": session_id,
            "user_id": user_id,
            "title": title,
            "messages": json.dumps(self._normalize_history_messages(messages), default=str),
            "tags": json.dumps(tags or []),
            "metadata": json.dumps(metadata or {}),
            "created_at": created_at,
            "updated_at": now,
        }

        cursor = self.execute(
            f"""
            UPDATE {table_name}
            SET title = ?, messages = ?, tags = ?, metadata = ?, updated_at = ?
            WHERE session_id = ? AND user_id = ?
            """,
            (
                row["title"],
                row["messages"],
                row["tags"],
                row["metadata"],
                row["updated_at"],
                session_id,
                user_id,
            ),
        )
        updated_count = cursor.rowcount
        cursor.close()

        if updated_count == 0:
            cursor = self.execute(
                f"""
                INSERT INTO {table_name}
                    (session_id, user_id, title, messages, tags, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["session_id"],
                    row["user_id"],
                    row["title"],
                    row["messages"],
                    row["tags"],
                    row["metadata"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )
            cursor.close()

        if not self.connection.autocommit:
            self.connection.commit()

        return self._decode_history_row(row)

    def append_user_history(
        self,
        user_id: str,
        session_id: str,
        messages: Union[str, Dict[str, Any], List[Union[str, Dict[str, Any]]]],
        table_name: str = DEFAULT_HISTORY_TABLE,
    ) -> bool:
        """Append messages to an existing user history session."""
        self._require_user_id(user_id)
        if not session_id:
            raise ValueError("session_id is required.")

        table_name = self._validate_table_name(table_name)
        self._ensure_history_table(table_name)
        session = self.get_user_history_session(user_id, session_id, table_name)
        if session is None:
            return False

        session["messages"].extend(self._normalize_history_messages(messages))
        cursor = self.execute(
            f"""
            UPDATE {table_name}
            SET messages = ?, updated_at = ?
            WHERE session_id = ? AND user_id = ?
            """,
            (
                json.dumps(session["messages"], default=str),
                self._utc_now(),
                session_id,
                user_id,
            ),
        )
        updated = cursor.rowcount > 0
        cursor.close()
        if not self.connection.autocommit:
            self.connection.commit()
        return updated

    def get_user_history_session(
        self,
        user_id: str,
        session_id: str,
        table_name: str = DEFAULT_HISTORY_TABLE,
    ) -> Optional[Dict[str, Any]]:
        """Fetch one history session for a user."""
        self._require_user_id(user_id)
        table_name = self._validate_table_name(table_name)
        self._ensure_history_table(table_name)

        row = self.fetchone(
            f"""
            SELECT session_id, user_id, title, messages, tags, metadata, created_at, updated_at
            FROM {table_name}
            WHERE session_id = ? AND user_id = ?
            """,
            (session_id, user_id),
        )
        return self._decode_history_row(row) if row else None

    def fetch_user_history(
        self,
        user_id: str,
        table_name: str = DEFAULT_HISTORY_TABLE,
        limit: int = 20,
        offset: int = 0,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch history sessions for a user, newest first."""
        self._require_user_id(user_id)
        table_name = self._validate_table_name(table_name)
        self._ensure_history_table(table_name)

        rows = self.fetchall(
            f"""
            SELECT session_id, user_id, title, messages, tags, metadata, created_at, updated_at
            FROM {table_name}
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,),
        )
        decoded = [self._decode_history_row(row) for row in rows]
        if tags:
            decoded = [
                row for row in decoded
                if any(tag in row.get("tags", []) for tag in tags)
            ]
        return decoded[offset: offset + limit]

    def search_user_history(
        self,
        user_id: str,
        query: str,
        table_name: str = DEFAULT_HISTORY_TABLE,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search a user's message history."""
        self._require_user_id(user_id)
        table_name = self._validate_table_name(table_name)
        self._ensure_history_table(table_name)

        rows = self.fetchall(
            f"""
            SELECT session_id, user_id, title, messages, tags, metadata, created_at, updated_at
            FROM {table_name}
            WHERE user_id = ? AND messages LIKE ?
            ORDER BY updated_at DESC
            """,
            (user_id, f"%{query}%"),
        )
        return [self._decode_history_row(row) for row in rows[:limit]]

    def delete_user_history(
        self,
        user_id: str,
        session_id: str,
        table_name: str = DEFAULT_HISTORY_TABLE,
    ) -> bool:
        """Delete one history session for a user."""
        self._require_user_id(user_id)
        table_name = self._validate_table_name(table_name)
        self._ensure_history_table(table_name)

        cursor = self.execute(
            f"DELETE FROM {table_name} WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        )
        deleted = cursor.rowcount > 0
        cursor.close()
        if not self.connection.autocommit:
            self.connection.commit()
        return deleted

    def _ensure_rulebook_table(self, table_name: str = DEFAULT_RULEBOOK_TABLE) -> None:
        """Create the rulebook table when it does not already exist."""
        if self.table_exists(table_name):
            return

        cursor = self.execute(
            f"""
            CREATE TABLE {table_name} (
                {RULEBOOK_ID_COLUMN} VARCHAR(255) PRIMARY KEY,
                {RULEBOOK_CONTENT_COLUMN} TEXT
            )
            """
        )
        cursor.close()
        if not self.connection.autocommit:
            self.connection.commit()

    def _normalize_rulebook_row(
        self,
        rulebook: Union[str, Dict[str, Any]],
        rulebook_id: Any = DEFAULT_RULEBOOK_ID,
        require_row_id: bool = False,
    ) -> Dict[str, Any]:
        """Convert rulebook input into a SQL row."""
        if isinstance(rulebook, str):
            row_id = rulebook_id
            rulebook_text = rulebook
        elif isinstance(rulebook, dict):
            row = dict(rulebook)
            row_id = rulebook_id
            for id_key in (RULEBOOK_ID_COLUMN, "_id", "rulebook_id"):
                if id_key in row:
                    row_id = row.pop(id_key)
                    break

            if require_row_id and row_id == DEFAULT_RULEBOOK_ID:
                raise ValueError(
                    "Each rulebook must include id, _id, or rulebook_id when saving multiple rulebooks."
                )

            if RULEBOOK_CONTENT_COLUMN in row:
                rulebook_text = row[RULEBOOK_CONTENT_COLUMN]
            elif "data" in row:
                rulebook_text = row["data"]
            else:
                rulebook_text = json.dumps(row)
        else:
            raise TypeError("rulebook must be a string or dictionary.")

        return {
            RULEBOOK_ID_COLUMN: row_id,
            RULEBOOK_CONTENT_COLUMN: rulebook_text,
        }

    def _upsert_rulebook_row(
        self,
        rulebook: Union[str, Dict[str, Any]],
        rulebook_id: Any = DEFAULT_RULEBOOK_ID,
        table_name: str = DEFAULT_RULEBOOK_TABLE,
        require_row_id: bool = False,
    ) -> int:
        """Save one rulebook row without creating duplicate id errors."""
        self._ensure_rulebook_table(table_name)
        row = self._normalize_rulebook_row(rulebook, rulebook_id, require_row_id)

        cursor = self.execute(
            f"""
            UPDATE {table_name}
            SET {RULEBOOK_CONTENT_COLUMN} = ?
            WHERE {RULEBOOK_ID_COLUMN} = ?
            """,
            (row[RULEBOOK_CONTENT_COLUMN], row[RULEBOOK_ID_COLUMN]),
        )
        updated_count = cursor.rowcount
        cursor.close()

        if updated_count == 0:
            cursor = self.execute(
                f"""
                INSERT INTO {table_name} ({RULEBOOK_ID_COLUMN}, {RULEBOOK_CONTENT_COLUMN})
                VALUES (?, ?)
                """,
                (row[RULEBOOK_ID_COLUMN], row[RULEBOOK_CONTENT_COLUMN]),
            )
            updated_count = cursor.rowcount
            cursor.close()

        if not self.connection.autocommit:
            self.connection.commit()

        return updated_count

    def insert_rulebook(
        self,
        rulebook: Union[str, Dict[str, Any], List[Union[str, Dict[str, Any]]]],
        rulebook_id: Any = DEFAULT_RULEBOOK_ID,
        table_name: str = DEFAULT_RULEBOOK_TABLE,
    ) -> Any:
        """Save rulebook data into the rulebook table by default."""
        if isinstance(rulebook, list):
            return [
                self._upsert_rulebook_row(
                    item,
                    rulebook_id=rulebook_id,
                    table_name=table_name,
                    require_row_id=len(rulebook) > 1,
                )
                for item in rulebook
            ]

        return self._upsert_rulebook_row(
            rulebook,
            rulebook_id=rulebook_id,
            table_name=table_name,
        )

    def get_rulebook(
        self,
        rulebook_id: Any = DEFAULT_RULEBOOK_ID,
        table_name: str = DEFAULT_RULEBOOK_TABLE,
    ) -> List[Dict[str, Any]]:
        """Retrieve rulebook rows from the rulebook table by id."""
        self._ensure_rulebook_table(table_name)
        return self.fetchall(
            f"""
            SELECT {RULEBOOK_ID_COLUMN}, {RULEBOOK_CONTENT_COLUMN}
            FROM {table_name}
            WHERE {RULEBOOK_ID_COLUMN} = ?
            """,
            (rulebook_id,),
        )

    def rulebook_prompt(
        self,
        rulebook_id: Any = DEFAULT_RULEBOOK_ID,
        table_name: str = DEFAULT_RULEBOOK_TABLE,
    ) -> str:
        """Generate a prompt string based on a rulebook row."""
        rows = self.get_rulebook(rulebook_id=rulebook_id, table_name=table_name)
        prompt_lines = ["Incorporate the following rules into your reasoning:"]

        for row in rows:
            prompt_lines.append(str(row.get(RULEBOOK_CONTENT_COLUMN, "")))

        return "\n".join(prompt_lines)

    def __enter__(self) -> "SQLService":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.connection and not self.connection.autocommit:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        self.close()
