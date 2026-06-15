import chromadb

from tm_embedder.embeddings import BGEEmbeddingFunction


class ChromaStore:

    def __init__(
        self,
        chroma_path: str,
        collection_name: str = "main_collection",
    ):
        self.client = chromadb.PersistentClient(
            path=chroma_path
        )

        self.collection = (
            self.client.get_collection(
                name=collection_name,
                embedding_function=BGEEmbeddingFunction(),
            )
        )
