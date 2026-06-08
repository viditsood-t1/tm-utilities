import unittest
from unittest.mock import MagicMock, patch

from tm_mongoService.mongo_connection import MongoService


class TestMongoService(unittest.TestCase):
    @patch("tm_mongoService.mongo_connection.MongoClient")
    def test_connect_uses_uri_and_pings(self, mock_client):
        client_instance = mock_client.return_value
        service = MongoService(uri="mongodb://localhost:27017", database="test_db", connect=False)

        returned_client = service.connect()

        mock_client.assert_called_once_with("mongodb://localhost:27017")
        client_instance.admin.command.assert_called_once_with("ping")
        self.assertIs(returned_client, client_instance)

    def test_database_property_raises_without_name(self):
        service = MongoService(connect=False)
        service._database_name = None
        service._client = MagicMock()

        with self.assertRaises(ValueError):
            _ = service.database

    def test_collection_lookup(self):
        service = MongoService(connect=False)
        service._client = MagicMock()
        service._database_name = "test_db"

        collection = service.collection("users")

        service._client.__getitem__.assert_called_once_with("test_db")
        self.assertEqual(collection, service._client["test_db"]["users"])

    def test_insert_find_delete_flow(self):
        service = MongoService(connect=False)
        collection_mock = MagicMock()
        service._get_collection = MagicMock(return_value=collection_mock)

        service.insert_one("users", {"name": "Alice"})
        collection_mock.insert_one.assert_called_once_with({"name": "Alice"})

        service.find_one("users", {"name": "Alice"}, {"_id": 0})
        collection_mock.find_one.assert_called_once_with({"name": "Alice"}, {"_id": 0})

        service.delete_one("users", {"name": "Alice"})
        collection_mock.delete_one.assert_called_once_with({"name": "Alice"})

    def test_count_documents(self):
        service = MongoService(connect=False)
        collection_mock = MagicMock()
        service._get_collection = MagicMock(return_value=collection_mock)

        service.count_documents("users", {"active": True})
        collection_mock.count_documents.assert_called_once_with({"active": True})


if __name__ == "__main__":
    unittest.main()
