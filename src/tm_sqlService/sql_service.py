import os
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union

try:
    import pyodbc
except ImportError as exc:
    raise ImportError(
        "pyodbc is required for tm_sqlService.SQLService. Install it with `pip install pyodbc`."
    ) from exc

DEFAULT_DB_ENV = "ODBC_CONNECTION_STRING"
DEFAULT_AUTOCOMMIT = False

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
