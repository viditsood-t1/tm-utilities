from .embedder import (
    ingest_document,
)
import os


def ask_file_path():

    file_path = input(
        "\nEnter file path: "
    ).strip()

    if not os.path.exists(file_path):
        raise FileNotFoundError(...)

    return file_path


def ask_metadata_case():

    print(
        "\nChoose Document Format"
    )

    print("1. Case 1 (With Metadata)")
    print("2. Case 2 (Without Metadata)")

    choice = input(
        "\nEnter choice: "
    ).strip()

    if choice == "1":
        return "case1"

    if choice == "2":
        return "case2"

    raise ValueError(
        "Invalid selection"
    )


def ask_embedding_mode():

    print(
        "\nChoose Embedding Mode"
    )

    print("1. Chunking")
    print("2. Page Wise")
    print("3. Full File")

    choice = input(
        "\nEnter choice: "
    ).strip()

    if choice == "1":
        return "chunk"

    if choice == "2":
        return "page"

    if choice == "3":
        return "file"

    raise ValueError(
        "Invalid selection"
    )


def ask_chunk_settings():

    chunk_size = int(
        input(
            "\nChunk Size: "
        )
    )

    chunk_overlap = int(
        input(
            "Chunk Overlap: "
        )
    )

    return (
        chunk_size,
        chunk_overlap,
    )


def main():

    print(
        "\n===== Document Embedder ====="
    )

    file_path = ask_file_path()

    metadata_case = ask_metadata_case()

    embedding_mode = ask_embedding_mode()

    chunk_size = 1000
    chunk_overlap = 200

    if embedding_mode == "chunk":

        (
            chunk_size,
            chunk_overlap,
        ) = ask_chunk_settings()

    ingest_document(
        file_path=file_path,
        metadata_case=metadata_case,
        embedding_mode=embedding_mode,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


if __name__ == "__main__":
    main()