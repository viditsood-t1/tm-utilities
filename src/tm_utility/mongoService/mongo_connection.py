import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

DEFAULT_URI = "mongodb://localhost:27017"
DEFAULT_URI_ENV = "MONGODB_URI"
DEFAULT_DB_ENV = "MONGODB_DB"
DEFAULT_RULEBOOK_COLLECTION = "rulebook"
DEFAULT_RULEBOOK_ID = "default"
DEFAULT_HISTORY_COLLECTION = "user_history"


class MongoService:
    """Service wrapper for MongoDB operations."""

    def __init__(
        self,
        uri: Optional[str] = None,
        database: Optional[str] = None,
        connect: bool = True,
        **kwargs: Any,
    ):
        self._uri = uri or os.getenv(DEFAULT_URI_ENV, DEFAULT_URI)
        self._database_name = database or os.getenv(DEFAULT_DB_ENV)
        self._client: Optional[MongoClient] = None
        self._kwargs = kwargs

        if connect:
            self.connect()

    def connect(self) -> MongoClient:
        """Create a MongoDB client and verify the connection."""
        if self._client is not None:
            return self._client

        try:
            self._client = MongoClient(self._uri, **self._kwargs)
            self._client.admin.command("ping")
            return self._client
        except PyMongoError as exc:
            raise RuntimeError(
                f"Failed to connect to MongoDB at {self._uri}: {exc}"
            ) from exc

    def close(self) -> None:
        """Close the MongoDB connection."""
        if self._client is not None:
            self._client.close()
            self._client = None

    @property
    def client(self) -> MongoClient:
        """Lazily create the MongoDB client when needed."""
        if self._client is None:
            self.connect()

        assert self._client is not None  # For type checkers
        return self._client

    @property
    def database(self) -> Database:
        """Return the configured MongoDB database."""
        if not self._database_name:
            raise ValueError(
                "MongoDB database name is required. Set database parameter or MONGODB_DB."
            )
        return self.client[self._database_name]

    def collection(self, name: str) -> Collection:
        """Return a collection instance for the configured database."""
        return self.database[name]

    def list_database_names(self) -> List[str]:
        return self.client.list_database_names()

    def list_collections(self) -> List[str]:
        return self.database.list_collection_names()

    def create_collection(self, name: str, **options: Any) -> Collection:
        return self.database.create_collection(name, **options)

    def drop_collection(self, name: str) -> Any:
        return self.database.drop_collection(name)

    def insert_one(
        self,
        collection: Union[str, Collection],
        document: Dict[str, Any],
    ) -> Any:
        return self._get_collection(collection).insert_one(document)

    def insert_many(
        self,
        collection: Union[str, Collection],
        documents: List[Dict[str, Any]],
    ) -> Any:
        return self._get_collection(collection).insert_many(documents)

    def find_one(
        self,
        collection: Union[str, Collection],
        filter: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        return self._get_collection(collection).find_one(filter or {}, projection)

    def find(
        self,
        collection: Union[str, Collection],
        filter: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, Any]] = None,
        sort: Optional[Sequence[tuple]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        cursor = self._get_collection(collection).find(filter or {}, projection)

        if sort:
            cursor = cursor.sort(list(sort))
        if limit:
            cursor = cursor.limit(limit)

        return list(cursor)

    def update_one(
        self,
        collection: Union[str, Collection],
        filter: Dict[str, Any],
        update: Dict[str, Any],
        upsert: bool = False,
    ) -> Any:
        return self._get_collection(collection).update_one(
            filter, update, upsert=upsert
        )

    def update_many(
        self,
        collection: Union[str, Collection],
        filter: Dict[str, Any],
        update: Dict[str, Any],
        upsert: bool = False,
    ) -> Any:
        return self._get_collection(collection).update_many(
            filter, update, upsert=upsert
        )

    def delete_one(
        self,
        collection: Union[str, Collection],
        filter: Dict[str, Any],
    ) -> Any:
        return self._get_collection(collection).delete_one(filter)

    def delete_many(
        self,
        collection: Union[str, Collection],
        filter: Dict[str, Any],
    ) -> Any:
        return self._get_collection(collection).delete_many(filter)

    def count_documents(
        self,
        collection: Union[str, Collection],
        filter: Optional[Dict[str, Any]] = None,
    ) -> int:
        return self._get_collection(collection).count_documents(filter or {})

    def aggregate(
        self,
        collection: Union[str, Collection],
        pipeline: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return list(self._get_collection(collection).aggregate(pipeline))

    def create_index(
        self,
        collection: Union[str, Collection],
        keys: Sequence[tuple],
        **options: Any,
    ) -> str:
        return self._get_collection(collection).create_index(keys, **options)

    def _get_collection(self, collection: Union[str, Collection]) -> Collection:
        if isinstance(collection, Collection):
            return collection
        return self.collection(collection)

    @staticmethod
    def _resolve_history_collection(
        collection: Union[str, Collection],
        table_name: Optional[Union[str, Collection]] = None,
    ) -> Union[str, Collection]:
        return table_name if table_name is not None else collection

    def _require_user_id(self, user_id: str) -> None:
        if not user_id:
            raise ValueError("user_id is required.")

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

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
            message.setdefault("timestamp", MongoService._utc_now())
            message.setdefault("metadata", {})
            normalized.append(message)

        return normalized

    def _ensure_history_indexes(
        self,
        collection: Union[str, Collection] = DEFAULT_HISTORY_COLLECTION,
    ) -> None:
        history_collection = self._get_collection(collection)
        history_collection.create_index("user_id")
        history_collection.create_index([("user_id", 1), ("updated_at", -1)])
        history_collection.create_index([("messages.content", "text")], sparse=True)

    def save_user_history(
        self,
        user_id: str,
        messages: Union[str, Dict[str, Any], List[Union[str, Dict[str, Any]]]],
        session_id: Optional[str] = None,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        collection: Union[str, Collection] = DEFAULT_HISTORY_COLLECTION,
        table_name: Optional[Union[str, Collection]] = None,
    ) -> Dict[str, Any]:
        """Create or replace one user history session."""
        self._require_user_id(user_id)
        collection = self._resolve_history_collection(collection, table_name)
        self._ensure_history_indexes(collection)

        now = self._utc_now()
        session_id = session_id or str(uuid.uuid4())
        existing = self._get_collection(collection).find_one({"_id": session_id})
        created_at = existing.get("created_at", now) if existing else now

        document = {
            "_id": session_id,
            "session_id": session_id,
            "user_id": user_id,
            "title": title,
            "tags": tags or [],
            "metadata": metadata or {},
            "messages": self._normalize_history_messages(messages),
            "created_at": created_at,
            "updated_at": now,
        }

        self._get_collection(collection).replace_one(
            {"_id": session_id, "user_id": user_id},
            document,
            upsert=True,
        )
        return document

    def append_user_history(
        self,
        user_id: str,
        session_id: str,
        messages: Union[str, Dict[str, Any], List[Union[str, Dict[str, Any]]]],
        collection: Union[str, Collection] = DEFAULT_HISTORY_COLLECTION,
        table_name: Optional[Union[str, Collection]] = None,
    ) -> bool:
        """Append messages to an existing user history session."""
        self._require_user_id(user_id)
        if not session_id:
            raise ValueError("session_id is required.")

        collection = self._resolve_history_collection(collection, table_name)
        normalized_messages = self._normalize_history_messages(messages)
        result = self._get_collection(collection).update_one(
            {"_id": session_id, "user_id": user_id},
            {
                "$push": {"messages": {"$each": normalized_messages}},
                "$set": {"updated_at": self._utc_now()},
            },
        )
        return result.matched_count > 0

    def get_user_history_session(
        self,
        user_id: str,
        session_id: str,
        collection: Union[str, Collection] = DEFAULT_HISTORY_COLLECTION,
        table_name: Optional[Union[str, Collection]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch one history session for a user."""
        self._require_user_id(user_id)
        collection = self._resolve_history_collection(collection, table_name)
        return self._get_collection(collection).find_one(
            {"_id": session_id, "user_id": user_id}
        )

    def fetch_user_history(
        self,
        user_id: str,
        collection: Union[str, Collection] = DEFAULT_HISTORY_COLLECTION,
        limit: int = 20,
        offset: int = 0,
        tags: Optional[List[str]] = None,
        table_name: Optional[Union[str, Collection]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch history sessions for a user, newest first."""
        self._require_user_id(user_id)
        collection = self._resolve_history_collection(collection, table_name)
        query: Dict[str, Any] = {"user_id": user_id}
        if tags:
            query["tags"] = {"$in": tags}

        cursor = (
            self._get_collection(collection)
            .find(query)
            .sort("updated_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return list(cursor)

    def search_user_history(
        self,
        user_id: str,
        query: str,
        collection: Union[str, Collection] = DEFAULT_HISTORY_COLLECTION,
        limit: int = 20,
        table_name: Optional[Union[str, Collection]] = None,
    ) -> List[Dict[str, Any]]:
        """Search a user's message history."""
        self._require_user_id(user_id)
        collection = self._resolve_history_collection(collection, table_name)
        self._ensure_history_indexes(collection)
        history_collection = self._get_collection(collection)

        try:
            cursor = history_collection.find(
                {"user_id": user_id, "$text": {"$search": query}},
                {"score": {"$meta": "textScore"}},
            ).sort([("score", {"$meta": "textScore"})]).limit(limit)
            return list(cursor)
        except PyMongoError:
            cursor = history_collection.find(
                {
                    "user_id": user_id,
                    "messages.content": {"$regex": query, "$options": "i"},
                }
            ).limit(limit)
            return list(cursor)

    def delete_user_history(
        self,
        user_id: str,
        session_id: str,
        collection: Union[str, Collection] = DEFAULT_HISTORY_COLLECTION,
        table_name: Optional[Union[str, Collection]] = None,
    ) -> bool:
        """Delete one history session for a user."""
        self._require_user_id(user_id)
        collection = self._resolve_history_collection(collection, table_name)
        result = self._get_collection(collection).delete_one(
            {"_id": session_id, "user_id": user_id}
        )
        return result.deleted_count > 0

    def _rulebook_filter(
        self,
        filter: Optional[Dict[str, Any]] = None,
        rulebook_id: Any = DEFAULT_RULEBOOK_ID,
    ) -> Dict[str, Any]:
        """Return a rulebook filter scoped to a single rulebook id."""
        rulebook_filter = dict(filter or {})
        rulebook_filter.setdefault("_id", rulebook_id)
        return rulebook_filter

    def _upsert_rulebook_document(
        self,
        rulebook: Union[str, Dict[str, Any]],
        collection: Union[str, Collection] = DEFAULT_RULEBOOK_COLLECTION,
        rulebook_id: Any = DEFAULT_RULEBOOK_ID,
        require_document_id: bool = False,
    ) -> Any:
        """Save one rulebook document without creating duplicate id errors."""
        if isinstance(rulebook, str):
            document = {"rulebook": rulebook}
        elif isinstance(rulebook, dict):
            document = dict(rulebook)
        else:
            raise TypeError("rulebook must be a string or dictionary.")

        if require_document_id and "_id" not in document:
            raise ValueError("Each rulebook must include _id when saving multiple rulebooks.")

        document.setdefault("_id", rulebook_id)
        update_fields = {key: value for key, value in document.items() if key != "_id"}
        update: Dict[str, Any] = {"$setOnInsert": {"_id": document["_id"]}}

        if update_fields:
            update["$set"] = update_fields

        return self.update_one(collection, {"_id": document["_id"]}, update, upsert=True)

    def insert_rulebook(
        self,
        rulebook: Union[str, Dict[str, Any], List[Union[str, Dict[str, Any]]]],
        rulebook_id: Any = DEFAULT_RULEBOOK_ID,
        collection: Union[str, Collection] = DEFAULT_RULEBOOK_COLLECTION,
    ) -> Any:
        """Save rulebook data into the rulebook collection by default."""
        if isinstance(rulebook, list):
            return [
                self._upsert_rulebook_document(
                    document,
                    collection=collection,
                    rulebook_id=rulebook_id,
                    require_document_id=len(rulebook) > 1,
                )
                for document in rulebook
            ]

        return self._upsert_rulebook_document(
            rulebook,
            collection=collection,
            rulebook_id=rulebook_id,
        )

    def get_rulebook(
        self,
        rulebook_id: Any = DEFAULT_RULEBOOK_ID,
        filter: Optional[Dict[str, Any]] = None,
        collection: Union[str, Collection] = DEFAULT_RULEBOOK_COLLECTION,
    ) -> List[Dict[str, Any]]:
        """Retrieve rulebook documents from the rulebook collection by default."""
        return self.find(collection, self._rulebook_filter(filter, rulebook_id))
    
    def rulebook_prompt(
        self,
        rulebook_id: Any = DEFAULT_RULEBOOK_ID,
        filter: Optional[Dict[str, Any]] = None,
        collection: Union[str, Collection] = DEFAULT_RULEBOOK_COLLECTION,
    ) -> str:
        """Generate a prompt string based on documents in the specified collection."""
        documents = self.find(collection, self._rulebook_filter(filter, rulebook_id))
        prompt_lines = ["Incorporate the following rules into your reasoning:"]
        for doc in documents:
            if "rulebook" in doc:
                prompt_lines.append(str(doc["rulebook"]))
            else:
                doc_str = ", ".join(f"{k}: {v}" for k, v in doc.items())
                prompt_lines.append(f"- {doc_str}")
        return "\n".join(prompt_lines)
