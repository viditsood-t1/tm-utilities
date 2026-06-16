import os
from pathlib import Path
from .loaders import load_document
from .metadata import parse_document
from .chunking import (
    chunk_document,
    page_embeddings,
    file_embedding,
)
from .chroma_store import ChromaStore
from .models import EmbeddingConfig
from .utils import (
    file_hash,
    make_embedding_id,
)

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}
def build_metadata(
    parsed_document,
    source_file,
    file_hash_value,
):

    metadata = {
        "source": os.path.basename(source_file),
        "file_hash": file_hash_value,
    }

    if parsed_document.metadata:

        metadata.update(
            {
                "document_title":
                    parsed_document.metadata.document_title,

                "document_description":
                    parsed_document.metadata.document_description,

                "author":
                    parsed_document.metadata.author,

                "tags":
                    parsed_document.metadata.tags,

                "url":
                    parsed_document.metadata.url,
            }
        )

    return metadata


def ingest_document(
    file_path: str,
    embedding_mode: str,
    metadata: bool = True,
    chroma_path: str = "./chroma_db",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
):

    # If a folder is passed, process all supported files
    if os.path.isdir(file_path):

        files = []

        for root, _, filenames in os.walk(file_path):
            for filename in filenames:

                ext = Path(filename).suffix.lower()

                if ext in SUPPORTED_EXTENSIONS:
                    files.append(
                        os.path.join(root, filename)
                    )

        if not files:
            print(
                f"No supported files found in {file_path}"
            )
            return

        print(
            f"Found {len(files)} files to process"
        )

        for file in files:
            try:
                ingest_document(
                    file_path=file,
                    metadata=metadata,
                    embedding_mode=embedding_mode,
                    chroma_path=chroma_path,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
            except Exception as e:
                print(
                    f"Failed to process {file}: {e}"
                )

        return

    config = EmbeddingConfig(
        embedding_mode=embedding_mode,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chroma_path=chroma_path,
    )

    parsed_document = load_document(
        file_path
    )

    parsed_document = parse_document(
        parsed_document,
        metadata,
    )

    store = ChromaStore(
        chroma_path=config.chroma_path,
        collection_name=config.collection_name,
    )

    fh = file_hash(file_path)

    if store.exists(fh):
        print(
            f"File already exists in collection: {file_path}"
        )
        return

    if embedding_mode == "chunk":

        records = chunk_document(
            parsed_document,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )

    elif embedding_mode == "page":

        records = page_embeddings(
            parsed_document
        )

    elif embedding_mode == "file":

        records = file_embedding(
            parsed_document
        )

    else:
        raise ValueError(
            "embedding_mode must be chunk/page/file"
        )

    ids = []
    documents = []
    metadatas = []

    base_metadata = build_metadata(
        parsed_document,
        file_path,
        fh,
    )

    for idx, record in enumerate(records):

        page_number = record["page_number"]
        content = record["content"]

        embedding_id = make_embedding_id(
            source_file=file_path,
            page_number=page_number,
            index=idx,
            content=content,
        )

        metadata = {
            **base_metadata,
            "page_number": page_number,
        }

        ids.append(
            embedding_id
        )

        documents.append(
            content
        )

        metadatas.append(
            metadata
        )

    store.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    print(
        f"Successfully embedded "
        f"{len(documents)} records "
        f"into collection "
        f"{config.collection_name}"
    )