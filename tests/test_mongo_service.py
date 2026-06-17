"""Tests for mongoService.MongoService (no live MongoDB required)."""
import unittest
from datetime import timezone
from unittest.mock import MagicMock, patch, PropertyMock

from tm_utility.mongoService.mongo_connection import (
    DEFAULT_HISTORY_COLLECTION,
    DEFAULT_RULEBOOK_COLLECTION,
    DEFAULT_RULEBOOK_ID,
    DEFAULT_URI,
    MongoService,
)


def _make_service(connect=False, database="testdb"):
    return MongoService(uri=DEFAULT_URI, database=database, connect=connect)


class TestConnect(unittest.TestCase):
    @patch("mongoService.mongo_connection.MongoClient")
    def test_connect_pings_server(self, MockClient):
        svc = _make_service()
        svc.connect()
        MockClient.return_value.admin.command.assert_called_once_with("ping")

    @patch("mongoService.mongo_connection.MongoClient")
    def test_connect_idempotent(self, MockClient):
        svc = _make_service()
        svc.connect()
        svc.connect()
        MockClient.assert_called_once()

    @patch("mongoService.mongo_connection.MongoClient", side_effect=Exception("err"))
    def test_connect_raises_runtime_error(self, _):
        svc = _make_service()
        with self.assertRaises(RuntimeError):
            svc.connect()

    @patch("mongoService.mongo_connection.MongoClient")
    def test_close_clears_client(self, MockClient):
        svc = _make_service()
        svc.connect()
        svc.close()
        self.assertIsNone(svc._client)

    def test_database_raises_without_name(self):
        svc = MongoService(uri=DEFAULT_URI, database=None, connect=False)
        with self.assertRaises(ValueError):
            _ = svc.database


class TestCRUD(unittest.TestCase):
    def setUp(self):
        self.svc = _make_service()
        self.mock_client = MagicMock()
        self.svc._client = self.mock_client
        self.mock_col = MagicMock()
        self.mock_client.__getitem__.return_value.__getitem__.return_value = self.mock_col

    def _col(self):
        return self.mock_col

    def test_insert_one(self):
        doc = {"a": 1}
        self.svc.insert_one("col", doc)
        self._col().insert_one.assert_called_once_with(doc)

    def test_insert_many(self):
        docs = [{"a": 1}, {"b": 2}]
        self.svc.insert_many("col", docs)
        self._col().insert_many.assert_called_once_with(docs)

    def test_find_one(self):
        self._col().find_one.return_value = {"x": 1}
        result = self.svc.find_one("col", {"x": 1})
        self.assertEqual(result, {"x": 1})

    def test_find_with_sort_and_limit(self):
        self._col().find.return_value.sort.return_value.limit.return_value = [{"a": 1}]
        result = self.svc.find("col", sort=[("a", 1)], limit=1)
        self.assertEqual(result, [{"a": 1}])

    def test_update_one(self):
        self.svc.update_one("col", {"_id": 1}, {"$set": {"a": 2}})
        self._col().update_one.assert_called_once()

    def test_update_many(self):
        self.svc.update_many("col", {"x": 1}, {"$set": {"x": 2}})
        self._col().update_many.assert_called_once()

    def test_delete_one(self):
        self.svc.delete_one("col", {"_id": 1})
        self._col().delete_one.assert_called_once_with({"_id": 1})

    def test_delete_many(self):
        self.svc.delete_many("col", {"x": 1})
        self._col().delete_many.assert_called_once_with({"x": 1})

    def test_count_documents(self):
        self._col().count_documents.return_value = 5
        self.assertEqual(self.svc.count_documents("col"), 5)

    def test_aggregate(self):
        self._col().aggregate.return_value = iter([{"total": 3}])
        result = self.svc.aggregate("col", [{"$count": "total"}])
        self.assertEqual(result, [{"total": 3}])

    def test_create_index(self):
        self._col().create_index.return_value = "idx"
        result = self.svc.create_index("col", [("a", 1)])
        self.assertEqual(result, "idx")


class TestNormalizeHistoryMessages(unittest.TestCase):
    def test_string_input(self):
        msgs = MongoService._normalize_history_messages("hello")
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[0]["content"], "hello")

    def test_dict_input(self):
        msgs = MongoService._normalize_history_messages({"role": "assistant", "content": "hi"})
        self.assertEqual(msgs[0]["role"], "assistant")

    def test_list_input(self):
        msgs = MongoService._normalize_history_messages(["a", "b"])
        self.assertEqual(len(msgs), 2)

    def test_invalid_type_raises(self):
        with self.assertRaises(TypeError):
            MongoService._normalize_history_messages([123])

    def test_defaults_are_set(self):
        msgs = MongoService._normalize_history_messages({})
        self.assertIn("role", msgs[0])
        self.assertIn("timestamp", msgs[0])
        self.assertIn("metadata", msgs[0])


class TestUserHistory(unittest.TestCase):
    def setUp(self):
        self.svc = _make_service()
        self.mock_client = MagicMock()
        self.svc._client = self.mock_client
        self.mock_col = MagicMock()
        self.mock_client.__getitem__.return_value.__getitem__.return_value = self.mock_col

    def test_save_user_history_requires_user_id(self):
        with self.assertRaises(ValueError):
            self.svc.save_user_history("", "hello")

    def test_save_user_history_upserts(self):
        self.mock_col.find_one.return_value = None
        result = self.svc.save_user_history("u1", "hello", session_id="s1")
        self.mock_col.replace_one.assert_called_once()
        self.assertEqual(result["user_id"], "u1")
        self.assertEqual(result["session_id"], "s1")

    def test_save_user_history_preserves_created_at(self):
        existing_time = "2024-01-01T00:00:00+00:00"
        self.mock_col.find_one.return_value = {"created_at": existing_time}
        result = self.svc.save_user_history("u1", "hello", session_id="s1")
        self.assertEqual(result["created_at"], existing_time)

    def test_append_user_history_requires_session_id(self):
        with self.assertRaises(ValueError):
            self.svc.append_user_history("u1", "", "msg")

    def test_append_user_history_returns_false_on_no_match(self):
        self.mock_col.update_one.return_value.matched_count = 0
        result = self.svc.append_user_history("u1", "s1", "msg")
        self.assertFalse(result)

    def test_append_user_history_returns_true_on_match(self):
        self.mock_col.update_one.return_value.matched_count = 1
        result = self.svc.append_user_history("u1", "s1", "msg")
        self.assertTrue(result)

    def test_get_user_history_session(self):
        self.mock_col.find_one.return_value = {"_id": "s1", "user_id": "u1"}
        result = self.svc.get_user_history_session("u1", "s1")
        self.assertEqual(result["_id"], "s1")

    def test_fetch_user_history_filters_by_tags(self):
        self.mock_col.find.return_value.sort.return_value.skip.return_value.limit.return_value = [
            {"user_id": "u1", "tags": ["a"]},
            {"user_id": "u1", "tags": ["b"]},
        ]
        result = self.svc.fetch_user_history("u1", tags=["a"])
        self.assertEqual(len(result), 1)

    def test_delete_user_history_returns_bool(self):
        self.mock_col.delete_one.return_value.deleted_count = 1
        self.assertTrue(self.svc.delete_user_history("u1", "s1"))
        self.mock_col.delete_one.return_value.deleted_count = 0
        self.assertFalse(self.svc.delete_user_history("u1", "s2"))

    def test_search_user_history_fallback_on_error(self):
        from pymongo.errors import PyMongoError
        self.mock_col.find.side_effect = [PyMongoError(), MagicMock(**{"limit.return_value": []})]
        result = self.svc.search_user_history("u1", "hello")
        self.assertEqual(result, [])


class TestRulebook(unittest.TestCase):
    def setUp(self):
        self.svc = _make_service()
        self.mock_client = MagicMock()
        self.svc._client = self.mock_client
        self.mock_col = MagicMock()
        self.mock_client.__getitem__.return_value.__getitem__.return_value = self.mock_col

    def test_insert_rulebook_string(self):
        self.svc.insert_rulebook("be polite")
        self.mock_col.update_one.assert_called_once()

    def test_insert_rulebook_dict(self):
        self.svc.insert_rulebook({"rulebook": "be concise"})
        self.mock_col.update_one.assert_called_once()

    def test_insert_rulebook_list_requires_ids(self):
        with self.assertRaises(ValueError):
            self.svc.insert_rulebook([{"rulebook": "r1"}, {"rulebook": "r2"}])

    def test_insert_rulebook_list_with_ids(self):
        self.svc.insert_rulebook([{"_id": "r1", "rulebook": "a"}, {"_id": "r2", "rulebook": "b"}])
        self.assertEqual(self.mock_col.update_one.call_count, 2)

    def test_get_rulebook(self):
        self.mock_col.find.return_value = [{"_id": "default", "rulebook": "rule1"}]
        result = self.svc.get_rulebook()
        self.assertEqual(len(result), 1)

    def test_rulebook_prompt_format(self):
        self.mock_col.find.return_value = [{"_id": "default", "rulebook": "Be helpful"}]
        prompt = self.svc.rulebook_prompt()
        self.assertIn("Incorporate the following rules", prompt)
        self.assertIn("Be helpful", prompt)

    def test_rulebook_prompt_no_rulebook_key(self):
        self.mock_col.find.return_value = [{"_id": "x", "key": "val"}]
        prompt = self.svc.rulebook_prompt()
        self.assertIn("key: val", prompt)

    def test_insert_rulebook_invalid_type(self):
        with self.assertRaises(TypeError):
            self.svc.insert_rulebook(123)


if __name__ == "__main__":
    unittest.main()
