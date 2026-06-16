# tests/test_utils.py

import hashlib

from vectorstore.utils import (
    clean_text,
    generate_sha256,
    make_embedding_id,
)


def test_clean_text_removes_extra_spaces():
    assert clean_text("  hello    world \n test ") == "hello world test"


def test_clean_text_handles_empty_string():
    assert clean_text("") == ""


def test_generate_sha256():
    expected = hashlib.sha256(
        b"hello"
    ).hexdigest()

    assert generate_sha256("hello") == expected


def test_make_embedding_id_is_deterministic():
    id1 = make_embedding_id(
        source_file="file.pdf",
        page_number=1,
        index=0,
        content="sample text",
    )

    id2 = make_embedding_id(
        source_file="file.pdf",
        page_number=1,
        index=0,
        content="sample text",
    )

    assert id1 == id2


def test_make_embedding_id_changes_when_content_changes():
    id1 = make_embedding_id(
        "file.pdf",
        1,
        0,
        "text1",
    )

    id2 = make_embedding_id(
        "file.pdf",
        1,
        0,
        "text2",
    )

    assert id1 != id2
