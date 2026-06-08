import os
from typing import Any, Dict, List, Optional, Sequence, Union

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

DEFAULT_URI = "mongodb://localhost:27017"
DEFAULT_URI_ENV = "MONGODB_URI"
DEFAULT_DB_ENV = "MONGODB_DB"


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
    
    def rulebook_prompt(self, collection: Union[str, Collection], filter: Optional[Dict[str, Any]] = None) -> str:
        """Generate a prompt string based on documents in the specified collection."""
        documents = self.find(collection, filter)
        prompt_lines = [f"Collection: {collection}"]
        for doc in documents:
            doc_str = ", ".join(f"{k}: {v}" for k, v in doc.items())
            prompt_lines.append(f"- {doc_str}")
        return "\n".join(prompt_lines)