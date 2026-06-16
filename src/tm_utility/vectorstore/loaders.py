from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
)

from .models import (
    ParsedDocument,
    DocumentPage,
)


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
}


def load_pdf(file_path: str) -> ParsedDocument:
    """
    Load PDF preserving page boundaries.
    """

    loader = PyPDFLoader(file_path)

    docs = loader.load()

    pages = []

    for idx, doc in enumerate(docs):

        pages.append(
            DocumentPage(
                page_number=idx + 1,
                content=doc.page_content,
            )
        )

    return ParsedDocument(
        metadata=None,
        pages=pages,
    )


def load_docx(file_path: str) -> ParsedDocument:
    """
    DOCX does not contain reliable page information.

    Entire document becomes a single page.
    """

    loader = Docx2txtLoader(file_path)

    docs = loader.load()

    full_text = "\n".join(
        d.page_content
        for d in docs
    )

    pages = [
        DocumentPage(
            page_number=1,
            content=full_text,
        )
    ]

    return ParsedDocument(
        metadata=None,
        pages=pages,
    )


def load_document(file_path: str) -> ParsedDocument:
    """
    Generic loader.
    """

    extension = Path(file_path).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {extension}"
        )

    if extension == ".pdf":
        return load_pdf(file_path)

    if extension == ".docx":
        return load_docx(file_path)

    raise ValueError(
        f"Unsupported file type: {extension}"
    )