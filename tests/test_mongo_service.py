import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from pymongo.errors import PyMongoError

from tm_utility.mongoService.mongo_connection import (
    MongoService,
    DEFAULT_HISTORY_COLLECTION,
    DEFAULT_RULEBOOK_COLLECTION,
)


@pytest.fixture
def service():
    return MongoService(connect=False)


def test_init_uses_defaults_without_connect():
    svc = MongoService(connect=False)
    assert svc._client is None


def test_connect_success():
    with patch("tm_utility.mongoService.mongo_connection.MongoClient") as mc:
        client = MagicMock()
        mc.return_value = client

        svc = MongoService(connect=False)
        result = svc.connect()

        client.admin.command.assert_called_once_with("ping")
        assert result is client


def test_connect_failure_raises_runtime_error():
    with patch("tm_utility.mongoService.mongo_connection.MongoClient", side_effect=PyMongoError("boom")):
        svc = MongoService(connect=False)
        with pytest.raises(RuntimeError):
            svc.connect()


def test_close_resets_client(service):
    client = MagicMock()
    service._client = client
    service.close()
    client.close.assert_called_once()
    assert service._client is None


def test_database_requires_name(service):
    with pytest.raises(ValueError):
        _ = service.database


def test_get_collection_from_string(service):
    coll = MagicMock()
    service.collection = MagicMock(return_value=coll)
    assert service._get_collection("users") == coll


def test_require_user_id(service):
    with pytest.raises(ValueError):
        service._require_user_id("")


def test_normalize_history_messages_string():
    msgs = MongoService._normalize_history_messages("hello")
    assert len(msgs) == 1
    assert msgs[0]["content"] == "hello"
    assert msgs[0]["role"] == "user"


def test_normalize_history_messages_dict():
    msgs = MongoService._normalize_history_messages({"content": "hi"})
    assert msgs[0]["content"] == "hi"
    assert "timestamp" in msgs[0]


def test_normalize_history_messages_invalid():
    with pytest.raises(TypeError):
        MongoService._normalize_history_messages([123])


def test_resolve_history_collection():
    assert MongoService._resolve_history_collection("a", "b") == "b"
    assert MongoService._resolve_history_collection("a") == "a"


def test_ensure_history_indexes(service):
    coll = MagicMock()
    service._get_collection = MagicMock(return_value=coll)

    service._ensure_history_indexes()

    assert coll.create_index.call_count == 3


def test_save_user_history(service):
    coll = MagicMock()
    coll.find_one.return_value = None
    service._get_collection = MagicMock(return_value=coll)
    service._ensure_history_indexes = MagicMock()

    doc = service.save_user_history("u1", "hello", session_id="s1")

    assert doc["_id"] == "s1"
    coll.replace_one.assert_called_once()


def test_append_user_history_success(service):
    result = MagicMock()
    result.matched_count = 1

    coll = MagicMock()
    coll.update_one.return_value = result
    service._get_collection = MagicMock(return_value=coll)

    assert service.append_user_history("u1", "s1", "msg") is True


def test_append_user_history_requires_session(service):
    with pytest.raises(ValueError):
        service.append_user_history("u1", "", "msg")


def test_get_user_history_session(service):
    coll = MagicMock()
    coll.find_one.return_value = {"_id": "s1"}
    service._get_collection = MagicMock(return_value=coll)

    result = service.get_user_history_session("u1", "s1")
    assert result["_id"] == "s1"


def test_fetch_user_history(service):
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = [{"_id": "1"}]

    coll = MagicMock()
    coll.find.return_value = cursor
    service._get_collection = MagicMock(return_value=coll)

    result = service.fetch_user_history("u1")
    assert result == [{"_id": "1"}]


def test_search_user_history_text_search(service):
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.limit.return_value = [{"_id": "1"}]

    coll = MagicMock()
    coll.find.return_value = cursor

    service._ensure_history_indexes = MagicMock()
    service._get_collection = MagicMock(return_value=coll)

    result = service.search_user_history("u1", "hello")
    assert result == [{"_id": "1"}]


def test_search_user_history_fallback_regex(service):
    coll = MagicMock()

    first_cursor = MagicMock()
    first_cursor.sort.side_effect = PyMongoError("no text")

    second_cursor = MagicMock()
    second_cursor.limit.return_value = [{"_id": "fallback"}]

    coll.find.side_effect = [first_cursor, second_cursor]

    service._ensure_history_indexes = MagicMock()
    service._get_collection = MagicMock(return_value=coll)

    result = service.search_user_history("u1", "hello")
    assert result == [{"_id": "fallback"}]


def test_delete_user_history(service):
    result = MagicMock()
    result.deleted_count = 1

    coll = MagicMock()
    coll.delete_one.return_value = result
    service._get_collection = MagicMock(return_value=coll)

    assert service.delete_user_history("u1", "s1") is True


def test_rulebook_filter(service):
    result = service._rulebook_filter({"x": 1}, "rb1")
    assert result["_id"] == "rb1"
    assert result["x"] == 1


def test_upsert_rulebook_document_string(service):
    service.update_one = MagicMock(return_value="ok")
    result = service._upsert_rulebook_document("rules")
    assert result == "ok"


def test_upsert_rulebook_document_invalid_type(service):
    with pytest.raises(TypeError):
        service._upsert_rulebook_document(123)


def test_upsert_rulebook_document_requires_id(service):
    with pytest.raises(ValueError):
        service._upsert_rulebook_document({}, require_document_id=True)


def test_insert_rulebook_list(service):
    service._upsert_rulebook_document = MagicMock(return_value="saved")
    result = service.insert_rulebook([{"_id": "1"}, {"_id": "2"}])
    assert result == ["saved", "saved"]


def test_get_rulebook(service):
    service.find = MagicMock(return_value=[{"rulebook": "r"}])
    result = service.get_rulebook()
    assert result == [{"rulebook": "r"}]


def test_rulebook_prompt(service):
    service.find = MagicMock(return_value=[
        {"rulebook": "Rule A"},
        {"name": "Rule B", "priority": 1},
    ])

    prompt = service.rulebook_prompt()

    assert "Rule A" in prompt
    assert "name: Rule B" in prompt


def test_find_applies_sort_and_limit(service):
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.__iter__.return_value = iter([{"a": 1}])

    coll = MagicMock()
    coll.find.return_value = cursor
    service._get_collection = MagicMock(return_value=coll)

    result = service.find("c", sort=[("a", 1)], limit=1)
    assert result == [{"a": 1}]
