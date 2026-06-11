from typing import Optional, Dict, Any

from src.tm_embedder.chroma_store import ChromaStore
from tm_embedder import main


# from src.tm_embedder.models import EmbeddingConfig


class Retriever:
    """
    Simple semantic retriever on top of the existing Chroma collection.
    """

    def __init__(
        self,
        chroma_path: str = "./chroma_db",
        collection_name: str = "main_collection",
    ):
        self.store = ChromaStore(
            chroma_path=chroma_path,
            collection_name=collection_name,
        )
        self.collection = self.store.get_collection()

    def search(
        self,
        query: str,
        k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ):
        """
        Semantic search.

        Example:
            retriever.search(
                "What is the cancellation policy?",
                k=3
            )
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=k,
            where=where,
        )

        matches = []

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        ids = results.get("ids", [[]])[0]

        for doc, meta, distance, doc_id in zip(
            docs,
            metas,
            distances,
            ids,
        ):
            matches.append(
                {
                    "id": doc_id,
                    "score": 1 - distance,  # cosine similarity
                    "document": doc,
                    "metadata": meta,
                }
            )

        return matches

    def search_by_file(
        self,
        query: str,
        file_hash: str,
        k: int = 5,
    ):
        return self.search(
            query=query,
            k=k,
            where={
                "file_hash": file_hash,
            },
        )



if __name__ == "__main__":
    retriever = Retriever(
        chroma_path="./chroma_db",
        collection_name="main_collection",
    )

    results = retriever.search(
        query=input("Enter query: "),
        k=5,
    )

    for idx, result in enumerate(results, start=1):
        print(f"\nResult {idx}")
        print(f"Score: {result['score']:.4f}")
        print(f"Metadata: {result['metadata']}")
        print(f"Document: {result['document']}")
        print("-" * 80)