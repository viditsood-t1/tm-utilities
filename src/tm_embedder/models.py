#models.py
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DocumentMetadata:
    document_title: str = ""
    document_description: str = ""
    author: str = ""
    tags: str = ""
    url: str = ""


@dataclass
class DocumentPage:
    page_number: int
    content: str


@dataclass
class ParsedDocument:
    metadata: Optional[DocumentMetadata]
    pages: List[DocumentPage]


@dataclass
class EmbeddingConfig:
    embedding_mode: str  # chunk | page | file

    chunk_size: int = 1000

    chunk_overlap: int = 200

    collection_name: str = "main_collection"

    model_name: str = "BAAI/bge-large-en-v1.5"

    chroma_path: str = "./chroma_db"