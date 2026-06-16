
import json
import pytest
from unittest.mock import MagicMock, patch

from tm_utility.sqlService.sql_service import (
    SQLService,
    _params_tuple,
    _row_to_dict,
)


@pytest.fixture
def service():
    return SQLService(connection_string="DRIVER=test", connect=False)


@pytest.fixture
def mock_connection():
    conn = MagicMock()
    conn.autocommit = False
    return conn


def test_params_tuple():
    assert _params_tuple(None) == []
    assert _params_tuple({"a": 1, "b": 2}) == (1, 2)
    assert _params_tuple([1, 2]) == [1, 2]
    assert _params_tuple("x") == ("x",)


def test_row_to_dict():
    cursor = MagicMock()
    cursor.description = [("id",), ("name",)]
    assert _row_to_dict(cursor, (1, "abc")) == {"id": 1, "name": "abc"}
    assert _row_to_dict(cursor, None) == {}


def test_build_connection_string_from_explicit():
    svc = SQLService(connection_string="ABC", connect=False)
    assert svc._build_connection_string() == "ABC"


def test_build_connection_string_from_parts():
    svc = SQLService(
        driver="ODBC Driver",
        server="srv",
        database="db",
        uid="u",
        pwd="p",
        connect=False,
    )
    cs = svc._build_connection_string()
    assert "DRIVER={ODBC Driver}" in cs
    assert "SERVER=srv" in cs
    assert "DATABASE=db" in cs


def test_build_connection_string_requires_input():
    with pytest.raises(ValueError):
        SQLService(connect=False)._build_connection_string()


@patch("tm_utility.sqlService.sql_service.pyodbc.connect")
def test_connect(mock_connect, service):
    service.connect()
    mock_connect.assert_called_once()


def test_close(service, mock_connection):
    service._connection = mock_connection
    service.close()
    mock_connection.close.assert_called_once()
    assert service._connection is None


def test_execute(service, mock_connection):
    cur = MagicMock()
    mock_connection.cursor.return_value = cur
    service._connection = mock_connection

    service.execute("select 1", [1])

    cur.execute.assert_called_once()


def test_transaction_commit(service, mock_connection):
    service._connection = mock_connection
    with service.transaction():
        pass
    mock_connection.commit.assert_called_once()


def test_transaction_rollback(service, mock_connection):
    service._connection = mock_connection
    with pytest.raises(RuntimeError):
        with service.transaction():
            raise RuntimeError()
    mock_connection.rollback.assert_called_once()


def test_build_insert_sql(service):
    sql, params = service._build_insert_sql("users", {"id": 1, "name": "a"})
    assert sql == "INSERT INTO users (id, name) VALUES (?, ?)"
    assert params == (1, "a")


def test_insert_one(service, mock_connection):
    cur = MagicMock()
    cur.lastrowid = 10
    mock_connection.cursor.return_value = cur
    service._connection = mock_connection

    result = service.insert_one("users", {"name": "john"})
    assert result == 10
    mock_connection.commit.assert_called_once()


def test_insert_many_empty(service):
    assert service.insert_many("users", []) == 0


def test_update_requires_values(service):
    with pytest.raises(ValueError):
        service.update("t", {}, "id=?")


def test_validate_table_name():
    assert SQLService._validate_table_name("schema.table_1") == "schema.table_1"
    with pytest.raises(ValueError):
        SQLService._validate_table_name("bad-table")


def test_require_user_id():
    with pytest.raises(ValueError):
        SQLService._require_user_id("")


def test_normalize_history_messages_string():
    result = SQLService._normalize_history_messages("hello")
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "hello"


def test_normalize_history_messages_invalid():
    with pytest.raises(TypeError):
        SQLService._normalize_history_messages([123])


def test_decode_history_row():
    row = {
        "messages": '[{"content":"hi"}]',
        "tags": '["a"]',
        "metadata": '{"x":1}',
    }
    decoded = SQLService._decode_history_row(row)
    assert decoded["tags"] == ["a"]
    assert decoded["metadata"]["x"] == 1


def test_normalize_rulebook_row_string(service):
    row = service._normalize_rulebook_row("rule")
    assert row["rulebook"] == "rule"


def test_normalize_rulebook_row_dict(service):
    row = service._normalize_rulebook_row({"id": "r1", "rulebook": "abc"})
    assert row["id"] == "r1"
    assert row["rulebook"] == "abc"


def test_normalize_rulebook_row_invalid(service):
    with pytest.raises(TypeError):
        service._normalize_rulebook_row(123)


def test_rulebook_prompt(service):
    service.get_rulebook = MagicMock(
        return_value=[{"rulebook": "Rule A"}, {"rulebook": "Rule B"}]
    )
    prompt = service.rulebook_prompt()
    assert "Rule A" in prompt and "Rule B" in prompt


def test_context_manager_success(service, mock_connection):
    service._connection = mock_connection
    with service:
        pass
    mock_connection.commit.assert_called()


def test_table_exists(service, mock_connection):
    cur = MagicMock()
    cur.fetchone.return_value = object()
    mock_connection.cursor.return_value = cur
    service._connection = mock_connection
    assert service.table_exists("users") is True


def test_get_columns(service, mock_connection):
    cur = MagicMock()
    row = MagicMock()
    row.column_name = "id"
    cur.fetchall.return_value = [row]
    mock_connection.cursor.return_value = cur
    service._connection = mock_connection

    assert service.get_columns("users") == ["id"]
