"""Tests for sqlService.SQLService (no live DB required)."""
import json
import unittest
from unittest.mock import MagicMock, patch, call

# Patch pyodbc before importing SQLService
import sys
sys.modules.setdefault("pyodbc", MagicMock())

from tm_utility.sqlService.sql_service import (
    DEFAULT_HISTORY_TABLE,
    DEFAULT_RULEBOOK_ID,
    DEFAULT_RULEBOOK_TABLE,
    RULEBOOK_CONTENT_COLUMN,
    RULEBOOK_ID_COLUMN,
    SQLService,
    _row_to_dict,
    _params_tuple,
)


def _make_service(**kwargs):
    """Return a SQLService with a mocked connection (no real ODBC)."""
    with patch("sqlService.sql_service.pyodbc.connect") as mock_connect:
        svc = SQLService(connection_string="DSN=test", connect=True, **kwargs)
        svc._connection = mock_connect.return_value
    return svc


def _mock_cursor(rows=None, rowcount=0, description=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = rows[0] if rows else None
    cursor.fetchall.return_value = rows or []
    cursor.fetchmany.return_value = rows or []
    cursor.rowcount = rowcount
    cursor.description = description or [("col",)]
    return cursor


class TestHelpers(unittest.TestCase):
    def test_row_to_dict_none(self):
        self.assertEqual(_row_to_dict(MagicMock(description=[("a",)]), None), {})

    def test_row_to_dict_maps_columns(self):
        cursor = MagicMock()
        cursor.description = [("id",), ("name",)]
        row = (1, "alice")
        self.assertEqual(_row_to_dict(cursor, row), {"id": 1, "name": "alice"})

    def test_params_tuple_none(self):
        self.assertEqual(_params_tuple(None), [])

    def test_params_tuple_dict(self):
        self.assertEqual(_params_tuple({"a": 1, "b": 2}), (1, 2))

    def test_params_tuple_list(self):
        self.assertEqual(_params_tuple([1, 2]), [1, 2])


class TestBuildConnectionString(unittest.TestCase):
    def test_explicit_string(self):
        svc = SQLService(connection_string="DSN=x", connect=False)
        self.assertEqual(svc._build_connection_string(), "DSN=x")

    def test_components(self):
        svc = SQLService(driver="SQL Server", server="localhost", database="db",
                         uid="u", pwd="p", connect=False)
        cs = svc._build_connection_string()
        self.assertIn("DRIVER={SQL Server}", cs)
        self.assertIn("SERVER=localhost", cs)
        self.assertIn("DATABASE=db", cs)

    def test_empty_raises(self):
        svc = SQLService(connect=False)
        with self.assertRaises(ValueError):
            svc._build_connection_string()


class TestConnect(unittest.TestCase):
    @patch("sqlService.sql_service.pyodbc.connect")
    def test_connect_sets_connection(self, mock_connect):
        svc = SQLService(connection_string="DSN=x", connect=False)
        svc.connect()
        self.assertIsNotNone(svc._connection)

    @patch("sqlService.sql_service.pyodbc.connect")
    def test_connect_idempotent(self, mock_connect):
        svc = SQLService(connection_string="DSN=x", connect=False)
        svc.connect()
        svc.connect()
        mock_connect.assert_called_once()

    @patch("sqlService.sql_service.pyodbc.connect")
    def test_close_clears_connection(self, mock_connect):
        svc = SQLService(connection_string="DSN=x", connect=True)
        svc.close()
        self.assertIsNone(svc._connection)


class TestTransaction(unittest.TestCase):
    def test_commits_on_success(self):
        svc = _make_service()
        svc._connection.autocommit = False
        with svc.transaction():
            pass
        svc._connection.commit.assert_called()

    def test_rolls_back_on_error(self):
        svc = _make_service()
        svc._connection.autocommit = False
        with self.assertRaises(RuntimeError):
            with svc.transaction():
                raise RuntimeError("boom")
        svc._connection.rollback.assert_called()

    def test_no_commit_when_autocommit(self):
        svc = _make_service()
        svc._connection.autocommit = True
        with svc.transaction():
            pass
        svc._connection.commit.assert_not_called()


class TestQueryMethods(unittest.TestCase):
    def setUp(self):
        self.svc = _make_service()
        self.cursor = _mock_cursor(rows=[(1, "a")], description=[("id",), ("name",)])
        self.svc._connection.cursor.return_value = self.cursor

    def test_fetchone_returns_dict(self):
        result = self.svc.fetchone("SELECT 1")
        self.assertEqual(result, {"id": 1, "name": "a"})

    def test_fetchone_returns_none_when_empty(self):
        self.cursor.fetchone.return_value = None
        result = self.svc.fetchone("SELECT 1")
        self.assertIsNone(result)

    def test_fetchall_returns_list(self):
        result = self.svc.fetchall("SELECT 1")
        self.assertIsInstance(result, list)

    def test_scalar_returns_first_value(self):
        self.cursor.fetchone.return_value = (42,)
        result = self.svc.scalar("SELECT COUNT(*) FROM t")
        self.assertEqual(result, 42)

    def test_scalar_returns_none_on_empty(self):
        self.cursor.fetchone.return_value = None
        self.assertIsNone(self.svc.scalar("SELECT 1"))


class TestInsertUpdateDelete(unittest.TestCase):
    def setUp(self):
        self.svc = _make_service()
        self.svc._connection.autocommit = True
        self.cursor = MagicMock()
        self.cursor.rowcount = 1
        self.cursor.description = [("id",)]
        self.svc._connection.cursor.return_value = self.cursor

    def test_insert_one(self):
        self.svc.insert_one("tbl", {"a": 1, "b": 2})
        sql = self.cursor.execute.call_args[0][0]
        self.assertIn("INSERT INTO tbl", sql)

    def test_insert_many(self):
        self.svc.insert_many("tbl", [{"a": 1}, {"a": 2}])
        self.cursor.executemany.assert_called_once()

    def test_insert_many_empty(self):
        result = self.svc.insert_many("tbl", [])
        self.assertEqual(result, 0)

    def test_update(self):
        count = self.svc.update("tbl", {"a": 1}, "id = ?", [99])
        self.assertEqual(count, 1)

    def test_update_empty_values_raises(self):
        with self.assertRaises(ValueError):
            self.svc.update("tbl", {}, "id = 1")

    def test_delete(self):
        self.svc.delete("tbl", "id = ?", [1])
        sql = self.cursor.execute.call_args[0][0]
        self.assertIn("DELETE FROM tbl", sql)

    def test_count(self):
        self.cursor.fetchone.return_value = (7,)
        result = self.svc.count("tbl")
        self.assertEqual(result, 7)

    def test_count_with_where(self):
        self.cursor.fetchone.return_value = (3,)
        result = self.svc.count("tbl", "active = ?", [1])
        self.assertEqual(result, 3)


class TestTableIntrospection(unittest.TestCase):
    def setUp(self):
        self.svc = _make_service()
        self.cursor = MagicMock()
        self.svc._connection.cursor.return_value = self.cursor

    def test_table_exists_true(self):
        self.cursor.fetchone.return_value = ("tbl",)
        self.assertTrue(self.svc.table_exists("tbl"))

    def test_table_exists_false(self):
        self.cursor.fetchone.return_value = None
        self.assertFalse(self.svc.table_exists("tbl"))

    def test_get_columns(self):
        row = MagicMock()
        row.column_name = "id"
        self.cursor.fetchall.return_value = [row]
        cols = self.svc.get_columns("tbl")
        self.assertEqual(cols, ["id"])


class TestNormalizeMessages(unittest.TestCase):
    def test_string(self):
        msgs = SQLService._normalize_history_messages("hi")
        self.assertEqual(msgs[0]["content"], "hi")
        self.assertEqual(msgs[0]["role"], "user")

    def test_dict(self):
        msgs = SQLService._normalize_history_messages({"role": "assistant", "content": "ok"})
        self.assertEqual(msgs[0]["role"], "assistant")

    def test_list(self):
        msgs = SQLService._normalize_history_messages(["a", "b"])
        self.assertEqual(len(msgs), 2)

    def test_invalid_raises(self):
        with self.assertRaises(TypeError):
            SQLService._normalize_history_messages([123])


class TestValidateTableName(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(SQLService._validate_table_name("user_history"), "user_history")

    def test_schema_qualified(self):
        self.assertEqual(SQLService._validate_table_name("dbo.tbl"), "dbo.tbl")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            SQLService._validate_table_name("")

    def test_injection_raises(self):
        with self.assertRaises(ValueError):
            SQLService._validate_table_name("tbl; DROP TABLE x--")


class TestUserHistory(unittest.TestCase):
    def _make(self):
        svc = _make_service()
        svc._connection.autocommit = True
        cursor = MagicMock()
        cursor.rowcount = 0
        cursor.description = [
            ("session_id",), ("user_id",), ("title",), ("messages",),
            ("tags",), ("metadata",), ("created_at",), ("updated_at",),
        ]
        svc._connection.cursor.return_value = cursor
        return svc, cursor

    def test_save_requires_user_id(self):
        svc, _ = self._make()
        with self.assertRaises(ValueError):
            svc.save_user_history("", "hello")

    def test_save_inserts_when_not_exists(self):
        svc, cursor = self._make()
        # table_exists → True (skip CREATE), fetchone for created_at → None
        cursor.fetchone.side_effect = [("user_history",), None, None]
        cursor.rowcount = 0
        result = svc.save_user_history("u1", "hello", session_id="s1")
        self.assertEqual(result["user_id"], "u1")

    def test_append_requires_session_id(self):
        svc, _ = self._make()
        with self.assertRaises(ValueError):
            svc.append_user_history("u1", "", "msg")

    def test_append_returns_false_when_session_missing(self):
        svc, cursor = self._make()
        cursor.fetchone.return_value = None
        result = svc.append_user_history("u1", "s1", "msg")
        self.assertFalse(result)

    def test_delete_returns_true(self):
        svc, cursor = self._make()
        cursor.fetchone.return_value = ("user_history",)  # table_exists
        cursor.rowcount = 1
        self.assertTrue(svc.delete_user_history("u1", "s1"))

    def test_delete_returns_false_when_not_found(self):
        svc, cursor = self._make()
        cursor.fetchone.return_value = ("user_history",)
        cursor.rowcount = 0
        self.assertFalse(svc.delete_user_history("u1", "s_gone"))

    def test_search_user_history(self):
        svc, cursor = self._make()
        cursor.fetchone.return_value = ("user_history",)
        encoded_row = (
            "s1", "u1", None,
            json.dumps([{"role": "user", "content": "hello"}]),
            "[]", "{}",
            "2024-01-01T00:00:00+00:00", "2024-01-01T00:00:00+00:00",
        )
        cursor.fetchall.return_value = [encoded_row]
        result = svc.search_user_history("u1", "hello")
        self.assertEqual(len(result), 1)


class TestRulebook(unittest.TestCase):
    def _make(self):
        svc = _make_service()
        svc._connection.autocommit = True
        cursor = MagicMock()
        cursor.rowcount = 1
        cursor.description = [(RULEBOOK_ID_COLUMN,), (RULEBOOK_CONTENT_COLUMN,)]
        cursor.fetchone.return_value = ("rulebook",)  # table_exists
        svc._connection.cursor.return_value = cursor
        return svc, cursor

    def test_insert_string(self):
        svc, cursor = self._make()
        svc.insert_rulebook("be helpful")
        self.assertTrue(cursor.execute.called)

    def test_insert_dict_with_content_key(self):
        svc, cursor = self._make()
        svc.insert_rulebook({RULEBOOK_CONTENT_COLUMN: "rule text"})
        self.assertTrue(cursor.execute.called)

    def test_insert_dict_with_id(self):
        svc, cursor = self._make()
        svc.insert_rulebook({"id": "r1", RULEBOOK_CONTENT_COLUMN: "text"})
        self.assertTrue(cursor.execute.called)

    def test_insert_list_single_no_id_ok(self):
        svc, cursor = self._make()
        svc.insert_rulebook(["rule text"])
        self.assertTrue(cursor.execute.called)

    def test_insert_list_multiple_requires_id(self):
        svc, _ = self._make()
        with self.assertRaises(ValueError):
            svc.insert_rulebook(["r1", "r2"])

    def test_insert_invalid_type(self):
        svc, _ = self._make()
        with self.assertRaises(TypeError):
            svc.insert_rulebook(999)

    def test_get_rulebook(self):
        svc, cursor = self._make()
        cursor.fetchall.return_value = [("default", "be concise")]
        result = svc.get_rulebook()
        self.assertEqual(len(result), 1)

    def test_rulebook_prompt(self):
        svc, cursor = self._make()
        cursor.fetchall.return_value = [("default", "be concise")]
        prompt = svc.rulebook_prompt()
        self.assertIn("Incorporate the following rules", prompt)
        self.assertIn("be concise", prompt)

    def test_rulebook_prompt_empty(self):
        svc, cursor = self._make()
        cursor.fetchall.return_value = []
        prompt = svc.rulebook_prompt()
        self.assertIn("Incorporate the following rules", prompt)


class TestContextManager(unittest.TestCase):
    @patch("sqlService.sql_service.pyodbc.connect")
    def test_context_manager_commits(self, mock_connect):
        mock_conn = MagicMock()
        mock_conn.autocommit = False
        mock_connect.return_value = mock_conn
        with SQLService(connection_string="DSN=x") as svc:
            pass
        mock_conn.commit.assert_called()

    @patch("sqlService.sql_service.pyodbc.connect")
    def test_context_manager_rollback_on_error(self, mock_connect):
        mock_conn = MagicMock()
        mock_conn.autocommit = False
        mock_connect.return_value = mock_conn
        try:
            with SQLService(connection_string="DSN=x"):
                raise ValueError("oops")
        except ValueError:
            pass
        mock_conn.rollback.assert_called()


if __name__ == "__main__":
    unittest.main()
