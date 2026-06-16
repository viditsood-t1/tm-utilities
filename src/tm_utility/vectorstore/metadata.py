import re

from .models import (
    ParsedDocument,
    DocumentMetadata,
    DocumentPage,
)


TITLE_PATTERN = re.compile(
    r"Document\s*Title:\s*(.*?)(?:\n|$)",
    re.IGNORECASE,
)

DESCRIPTION_PATTERN = re.compile(
    r"Document\s*Description:\s*(.*?)(?:\n|$)",
    re.IGNORECASE,
)

AUTHOR_PATTERN = re.compile(
    r"Author:\s*(.*?)(?:\n|$)",
    re.IGNORECASE,
)

TAGS_PATTERN = re.compile(
    r"Tags:\s*(.*?)(?:\n|$)",
    re.IGNORECASE,
)

URL_PATTERN = re.compile(
    r"URL:\s*(.*?)(?:\n|$)",
    re.IGNORECASE,
)


def extract_field(pattern, text: str) -> str:
    match = pattern.search(text)

    if not match:
        return ""

    return match.group(1).strip()


def extract_document_content(text: str) -> str:
    """
    Extract content after 'Document Content'
    """

    pattern = re.compile(
        r"Document\s*Content(.*)",
        re.IGNORECASE | re.DOTALL,
    )

    match = pattern.search(text)

    if not match:
        return text.strip()

    return match.group(1).strip()


def parse_case1(
    parsed_document: ParsedDocument,
) -> ParsedDocument:

    full_text = "\n".join(
        page.content
        for page in parsed_document.pages
    )

    metadata = DocumentMetadata(
        document_title=extract_field(
            TITLE_PATTERN,
            full_text,
        ),
        document_description=extract_field(
            DESCRIPTION_PATTERN,
            full_text,
        ),
        author=extract_field(
            AUTHOR_PATTERN,
            full_text,
        ),
        tags=extract_field(
            TAGS_PATTERN,
            full_text,
        ),
        url=extract_field(
            URL_PATTERN,
            full_text,
        ),
    )

    content = extract_document_content(
        full_text
    )

    parsed_document.metadata = metadata

    parsed_document.pages[0] = DocumentPage(
            page_number=1,
            content=content,
        )

    return parsed_document


def parse_case2(
    parsed_document: ParsedDocument,
) -> ParsedDocument:

    parsed_document.metadata = None

    return parsed_document


def parse_document(
    parsed_document: ParsedDocument,
    metadata: bool = True,
) -> ParsedDocument:

    if metadata:
        return parse_case1(parsed_document)

    return parse_case2(parsed_document)