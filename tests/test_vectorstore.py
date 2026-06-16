
import pytest
from types import SimpleNamespace

from tm_utility.vectorstore.models import (
    DocumentPage,
    ParsedDocument,
    DocumentMetadata,
)
from tm_utility.vectorstore.utils import (
    clean_text,
    generate_sha256,
    make_embedding_id,
)
from tm_utility.vectorstore.metadata import (
    extract_field,
    extract_document_content,
    TITLE_PATTERN,
    parse_document,
)
from tm_utility.vectorstore.chunking import (
    page_embeddings,
    file_embedding,
    chunk_document,
)
from tm_utility.vectorstore.embedder import build_metadata
from tm_utility.vectorstore.loaders import load_document
from tm_utility.vectorstore.retriever import retrieve


def sample_doc():
    return ParsedDocument(
        metadata=None,
        pages=[
            DocumentPage(page_number=1, content="Hello World"),
            DocumentPage(page_number=2, content="Second Page"),
        ],
    )


# ---------- utils.py ----------

def test_clean_text():
    assert clean_text("a   b\n\nc") == "a b c"
    assert clean_text("") == ""


def test_generate_sha256_stable():
    assert generate_sha256("abc") == generate_sha256("abc")
    assert generate_sha256("abc") != generate_sha256("xyz")


def test_make_embedding_id_stable():
    v1 = make_embedding_id("file.pdf", 1, 0, "content")
    v2 = make_embedding_id("file.pdf", 1, 0, "content")
    assert v1 == v2


# ---------- metadata.py ----------

def test_extract_field():
    text = "Document Title: My Title"
    assert extract_field(TITLE_PATTERN, text) == "My Title"


def test_extract_document_content():
    text = "Document Content\nActual content"
    assert extract_document_content(text) == "Actual content"


def test_parse_document_with_metadata():
    doc = ParsedDocument(
        metadata=None,
        pages=[
            DocumentPage(
                1,
                "Document Title: Test\nAuthor: John\nDocument Content\nBody"
            )
        ],
    )

    parsed = parse_document(doc, metadata=True)

    assert parsed.metadata.document_title == "Test"
    assert parsed.metadata.author == "John"
    assert parsed.pages[0].content == "Body"


def test_parse_document_without_metadata():
    doc = sample_doc()
    parsed = parse_document(doc, metadata=False)
    assert parsed.metadata is None


# ---------- chunking.py ----------

def test_page_embeddings():
    result = page_embeddings(sample_doc())
    assert len(result) == 2
    assert result[0]["page_number"] == 1


def test_file_embedding():
    result = file_embedding(sample_doc())
    assert len(result) == 1
    assert "Hello World" in result[0]["content"]
    assert "Second Page" in result[0]["content"]


def test_chunk_document():
    doc = ParsedDocument(
        metadata=None,
        pages=[DocumentPage(1, "A" * 50)]
    )

    chunks = chunk_document(
        doc,
        chunk_size=10,
        chunk_overlap=0,
    )

    assert len(chunks) > 1
    assert all("content" in c for c in chunks)


# ---------- embedder.py ----------

def test_build_metadata_with_document_metadata():
    parsed = ParsedDocument(
        metadata=DocumentMetadata(
            document_title="Title",
            document_description="Desc",
            author="Author",
            tags="tag1",
            url="http://x.com",
        ),
        pages=[],
    )

    meta = build_metadata(
        parsed,
        "/tmp/file.pdf",
        "hash123",
    )

    assert meta["source"] == "file.pdf"
    assert meta["file_hash"] == "hash123"
    assert meta["document_title"] == "Title"


def test_build_metadata_without_document_metadata():
    parsed = ParsedDocument(
        metadata=None,
        pages=[],
    )

    meta = build_metadata(
        parsed,
        "/tmp/file.pdf",
        "hash123",
    )

    assert meta == {
        "source": "file.pdf",
        "file_hash": "hash123",
    }


# ---------- loaders.py ----------

def test_load_document_invalid_extension(tmp_path):
    file = tmp_path / "bad.txt"
    file.write_text("x")

    with pytest.raises(ValueError):
        load_document(str(file))


# ---------- embeddings.py ----------

def test_get_device_cpu(monkeypatch):
    from tm_utility.vectorstore import embeddings

    monkeypatch.setattr(
        embeddings.torch.cuda,
        "is_available",
        lambda: False,
    )

    assert embeddings.get_device() == "cpu"


def test_embed_texts(monkeypatch):
    from tm_utility.vectorstore import embeddings

    class FakeModel:
        def encode(self, *args, **kwargs):
            return SimpleNamespace(
                tolist=lambda: [[0.1, 0.2]]
            )

    monkeypatch.setattr(
        embeddings,
        "get_embedding_model",
        lambda: FakeModel(),
    )

    result = embeddings.embed_texts(["hello"])
    assert result == [[0.1, 0.2]]


# ---------- retriever.py ----------

def test_retrieve(monkeypatch):
    class FakeCollection:
        def query(self, **kwargs):
            return {
                "documents": [["doc1"]],
                "metadatas": [[{"a": 1}]],
                "distances": [[0.2]],
            }

    class FakeStore:
        def __init__(self, *args, **kwargs):
            self.collection = FakeCollection()

    monkeypatch.setattr(
        "tm_utility.vectorstore.retriever.ChromaStore",
        FakeStore,
    )

    results = retrieve("test")

    assert len(results) == 1
    assert results[0]["content"] == "doc1"
    assert results[0]["score"] == pytest.approx(0.8)


# ---------- chroma_store.py ----------

def test_chroma_exists():
    class FakeCollection:
        def get(self, **kwargs):
            return {"ids": ["1"]}

    store = SimpleNamespace(collection=FakeCollection())

    from tm_utility.vectorstore.chroma_store import ChromaStore

    assert ChromaStore.exists(store, "hash") is True
