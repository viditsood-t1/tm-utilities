import unittest
from unittest.mock import MagicMock, patch

from tm_sqlService.sql_service import SQLService


class TestSQLService(unittest.TestCase):
    @patch("tm_sqlService.sql_service.pyodbc.connect")
    def test_connect_uses_connection_string(self, mock_connect):
        mock_connection = MagicMock()
        mock_connection.autocommit = False
        mock_connect.return_value = mock_connection

        service = SQLService(
            connection_string="DRIVER={SQL Server};SERVER=localhost;DATABASE=test_db;",
            connect=False,
        )

        returned = service.connect()

        mock_connect.assert_called_once_with(
            "DRIVER={SQL Server};SERVER=localhost;DATABASE=test_db;",
            autocommit=False,
            timeout=0,
        )
        self.assertIs(returned, mock_connection)

    def test_build_connection_string_with_params(self):
        service = SQLService(
            driver="SQL Server",
            server="localhost",
            database="test_db",
            uid="user",
            pwd="pass",
            connect=False,
        )

        self.assertEqual(
            service._build_connection_string(),
            "DRIVER={SQL Server};SERVER=localhost;DATABASE=test_db;UID=user;PWD=pass",
        )

    def test_close_closes_connection(self):
        service = SQLService(connect=False)
        connection = MagicMock()
        service._connection = connection

        service.close()

        connection.close.assert_called_once()
        self.assertIsNone(service._connection)

    @patch("tm_sqlService.sql_service.SQLService.execute")
    def test_fetchall_returns_dicts(self, mock_execute):
        cursor = MagicMock()
        cursor.description = [("id",), ("name",)]
        cursor.fetchall.return_value = [(1, "Alice"), (2, "Bob")]
        mock_execute.return_value = cursor

        service = SQLService(connect=False)
        rows = service.fetchall("SELECT id, name FROM users")

        self.assertEqual(rows, [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}])
        cursor.close.assert_called_once()

    @patch("tm_sqlService.sql_service.SQLService.execute")
    def test_scalar_returns_first_value(self, mock_execute):
        cursor = MagicMock()
        cursor.fetchone.return_value = (42,)
        mock_execute.return_value = cursor

        service = SQLService(connect=False)
        value = service.scalar("SELECT COUNT(*) FROM users")

        self.assertEqual(value, 42)
        cursor.close.assert_called_once()

    @patch("tm_sqlService.sql_service.pyodbc.connect")
    def test_transaction_commit(self, mock_connect):
        mock_connection = MagicMock()
        mock_connection.autocommit = False
        mock_connect.return_value = mock_connection
        service = SQLService(connection_string="dsn=test", connect=False)
        service._connection = mock_connection

        with service.transaction():
            pass

        mock_connection.commit.assert_called_once()
        mock_connection.rollback.assert_not_called()

    @patch("tm_sqlService.sql_service.pyodbc.connect")
    def test_transaction_rollback_on_error(self, mock_connect):
        mock_connection = MagicMock()
        mock_connection.autocommit = False
        mock_connect.return_value = mock_connection
        service = SQLService(connection_string="dsn=test", connect=False)
        service._connection = mock_connection

        with self.assertRaises(RuntimeError):
            with service.transaction():
                raise RuntimeError("boom")

        mock_connection.rollback.assert_called_once()

    def test_table_exists_with_tables_cursor(self):
        service = SQLService(connect=False)
        cursor = MagicMock()
        cursor.fetchone.return_value = ("users",)
        service._connection = MagicMock()
        service._connection.cursor.return_value = cursor

        exists = service.table_exists("users")

        cursor.tables.assert_called_once_with(table="users")
        self.assertTrue(exists)

    def test_get_columns_returns_column_names(self):
        service = SQLService(connect=False)
        cursor = MagicMock()
        cursor.fetchall.return_value = [MagicMock(column_name="id"), MagicMock(column_name="name")]
        service._connection = MagicMock()
        service._connection.cursor.return_value = cursor

        columns = service.get_columns("users")

        cursor.columns.assert_called_once_with(table="users")
        self.assertEqual(columns, ["id", "name"])

    @patch("tm_sqlService.sql_service.SQLService.execute")
    def test_insert_one_commits_and_returns_lastrowid(self, mock_execute):
        cursor = MagicMock()
        cursor.lastrowid = 7
        mock_execute.return_value = cursor

        service = SQLService(connect=False)
        service._connection = MagicMock()
        service._connection.autocommit = False

        row_id = service.insert_one("users", {"name": "Alice"})

        self.assertEqual(row_id, 7)
        service._connection.commit.assert_called_once()
        cursor.close.assert_called_once()

    @patch("tm_sqlService.sql_service.SQLService.execute")
    def test_update_commits_and_returns_rowcount(self, mock_execute):
        cursor = MagicMock()
        cursor.rowcount = 1
        mock_execute.return_value = cursor

        service = SQLService(connect=False)
        service._connection = MagicMock()
        service._connection.autocommit = False

        affected = service.update("users", {"active": 0}, "id = ?", (1,))

        self.assertEqual(affected, 1)
        service._connection.commit.assert_called_once()
        cursor.close.assert_called_once()

    @patch("tm_sqlService.sql_service.SQLService.execute")
    def test_delete_commits_and_returns_rowcount(self, mock_execute):
        cursor = MagicMock()
        cursor.rowcount = 2
        mock_execute.return_value = cursor

        service = SQLService(connect=False)
        service._connection = MagicMock()
        service._connection.autocommit = False

        deleted = service.delete("users", "active = ?", (0,))

        self.assertEqual(deleted, 2)
        service._connection.commit.assert_called_once()
        cursor.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
