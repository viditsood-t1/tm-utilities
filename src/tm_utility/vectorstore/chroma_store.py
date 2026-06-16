import chromadb

from .embeddings import BGEEmbeddingFunction


DEFAULT_COLLECTION = "main_collection"


class ChromaStore:

    def __init__(
        self,
        chroma_path: str,
        collection_name: str = DEFAULT_COLLECTION,
    ):

        self.client = chromadb.PersistentClient(
            path=chroma_path
        )

        self.collection = (
            self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=BGEEmbeddingFunction(),
                metadata={
                    "hnsw:space": "cosine"
                },
            )
        )

    def count(self) -> int:
        return self.collection.count()

    def upsert(
        self,
        ids,
        documents,
        metadatas,
    ):
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def get_collection(self):
        return self.collection

    def exists(
        self,
        file_hash: str,
    ) -> bool:

        result = self.collection.get(
            where={
                "file_hash": file_hash
            },
            limit=1,
        )

        return len(result["ids"]) > 0