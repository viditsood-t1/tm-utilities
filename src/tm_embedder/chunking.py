from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
)

from .models import (
    ParsedDocument,
)


def chunk_document(
    parsed_document: ParsedDocument,
    chunk_size: int,
    chunk_overlap: int,
):
    """
    Chunk-level embedding.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks = []

    for page in parsed_document.pages:

        page_chunks = splitter.split_text(
            page.content
        )

        for chunk in page_chunks:

            chunks.append(
                {
                    "page_number": page.page_number,
                    "content": chunk,
                }
            )

    return chunks


def page_embeddings(
    parsed_document: ParsedDocument,
):
    """
    One page = one embedding.
    """

    results = []

    for page in parsed_document.pages:

        results.append(
            {
                "page_number": page.page_number,
                "content": page.content,
            }
        )

    return results


def file_embedding(
    parsed_document: ParsedDocument,
):
    """
    Entire file = one embedding.
    """

    full_text = "\n".join(
        page.content
        for page in parsed_document.pages
    )

    return [
        {
            "page_number": 1,
            "content": full_text,
        }
    ]