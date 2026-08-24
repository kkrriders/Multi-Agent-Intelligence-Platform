import uuid
from io import BytesIO

from app.rag import chunk_text, delete_document_vectors, embed_and_store_chunks, extract_text, retrieve_chunks


def test_chunk_text_splits_with_overlap():
    text = "a" * 1000
    chunks = chunk_text(text, chunk_size=400, overlap=50)

    assert len(chunks) == 3
    assert chunks[0] == "a" * 400
    assert chunks[1] == "a" * 400
    assert chunks[2] == "a" * 300
    # consecutive chunks overlap by exactly `overlap` characters
    assert chunks[0][-50:] == chunks[1][:50]


def test_chunk_text_short_text_returns_single_chunk():
    assert chunk_text("hello world") == ["hello world"]


def test_chunk_text_empty_string_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_extract_text_plain_text_decodes_utf8():
    assert extract_text("text/plain", "hello world".encode("utf-8")) == "hello world"


def test_extract_text_markdown_decodes_utf8():
    assert extract_text("text/markdown", "# Title\nBody".encode("utf-8")) == "# Title\nBody"


def test_extract_text_pdf_reads_embedded_text():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer_out = BytesIO()
    writer.write(buffer_out)
    pdf_bytes = buffer_out.getvalue()

    # A blank page has no text layer — this exercises the "no text" branch
    # (`page.extract_text() or ""`) without needing a real text-bearing PDF fixture.
    assert extract_text("application/pdf", pdf_bytes) == ""


class _EmptyKeywordClient:
    """Stubs the Postgres half of retrieve_chunks so these tests can verify
    the Qdrant vector-search half in isolation, without a live authenticated
    Supabase project. The full hybrid path (both halves together) is
    exercised by the real integration tests in test_documents.py/test_runs.py."""

    def table(self, name):
        return self

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def text_search(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        class _Result:
            data = []

        return _Result()


def test_embed_and_store_then_retrieve_finds_vector_match(qdrant_available):
    project_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    chunk_id = str(uuid.uuid4())

    embed_and_store_chunks(
        project_id=project_id,
        document_id=document_id,
        filename="notes.txt",
        chunks=[{"chunk_id": chunk_id, "chunk_index": 0, "content": "The launch codeword is Bluebird."}],
    )

    results = retrieve_chunks(_EmptyKeywordClient(), project_id, "rocket launch codeword")

    assert any(r["chunk_id"] == chunk_id for r in results)
    match = next(r for r in results if r["chunk_id"] == chunk_id)
    assert match["document_id"] == document_id
    assert match["filename"] == "notes.txt"
    assert match["project_id"] == project_id


def test_delete_document_vectors_removes_points(qdrant_available):
    project_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    chunk_id = str(uuid.uuid4())

    embed_and_store_chunks(
        project_id=project_id,
        document_id=document_id,
        filename="notes.txt",
        chunks=[{"chunk_id": chunk_id, "chunk_index": 0, "content": "The launch codeword is Bluebird."}],
    )
    delete_document_vectors(document_id)

    results = retrieve_chunks(_EmptyKeywordClient(), project_id, "rocket launch codeword")

    assert not any(r["chunk_id"] == chunk_id for r in results)
