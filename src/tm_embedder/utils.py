import hashlib
import re


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def generate_sha256(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def file_hash(file_path: str) -> str:
    h = hashlib.sha256()

    with open(file_path, "rb") as f:
        for chunk in iter(
            lambda: f.read(8192),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def make_embedding_id(
    source_file: str,
    page_number: int,
    index: int,
    content: str,
) -> str:
    raw = (
        f"{source_file}|"
        f"{page_number}|"
        f"{index}|"
        f"{content}"
    )

    return generate_sha256(raw)