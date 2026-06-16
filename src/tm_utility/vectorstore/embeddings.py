from typing import List

import torch
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer


MODEL_NAME = "BAAI/bge-large-en-v1.5"

_model = None


def get_device() -> str:
    """
    Auto detect GPU/CPU.
    """
    if torch.cuda.is_available():
        return "cuda"

    return "cpu"


def get_embedding_model() -> SentenceTransformer:
    """
    Singleton model loader.
    Loads only once during application lifetime.
    """

    global _model

    if _model is None:
        _model = SentenceTransformer(
            MODEL_NAME,
            device=get_device(),
        )

    return _model


class BGEEmbeddingFunction(EmbeddingFunction):
    """
    ChromaDB embedding function.
    """

    def __init__(self):
        self.model = get_embedding_model()

    def __call__(
        self,
        input: Documents,
    ) -> Embeddings:

        embeddings = self.model.encode(
            input,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return embeddings.tolist()


def embed_texts(
    texts: List[str],
) -> List[List[float]]:
    """
    Direct embedding utility.
    """

    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return embeddings.tolist()