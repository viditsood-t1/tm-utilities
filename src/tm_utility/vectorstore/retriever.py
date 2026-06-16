from .chroma_store import ChromaStore


def retrieve(
    query: str,
    chroma_path: str = "./chroma_db",
    collection_name: str = "main_collection",
    top_k: int = 5,
):
    store = ChromaStore(
        chroma_path=chroma_path,
        collection_name=collection_name,
    )

    results = store.collection.query(
        query_texts=[query],
        n_results=top_k,
    )

    output = []

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for doc, meta, distance in zip(
        documents,
        metadatas,
        distances,
    ):
        output.append(
            {
                "content": doc,
                "metadata": meta,
                "score": 1 - distance,
            }
        )

    return output