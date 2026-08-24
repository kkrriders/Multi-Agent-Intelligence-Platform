from io import BytesIO

from pypdf import PdfReader
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding

from app.config import settings

COLLECTION = "documents"
BUCKET = "documents"
SCORE_THRESHOLD = 0.5
KEYWORD_MATCH_SCORE = 0.5
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

_client = QdrantClient(url=settings.qdrant_url)
_embedder: TextEmbedding | None = None


def _ensure_collection() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
        if not _client.collection_exists(COLLECTION):
            _client.create_collection(
                collection_name=COLLECTION,
                vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE),
            )
    return _embedder


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def extract_text(mime_type: str, content: bytes) -> str:
    if mime_type == "application/pdf":
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return content.decode("utf-8")


def embed_and_store_chunks(project_id: str, document_id: str, filename: str, chunks: list[dict]) -> None:
    if not chunks:
        return
    embedder = _ensure_collection()
    vectors = list(embedder.embed([chunk["content"] for chunk in chunks]))
    _client.upsert(
        collection_name=COLLECTION,
        points=[
            models.PointStruct(
                id=chunk["chunk_id"],
                vector=vectors[i].tolist(),
                payload={
                    "project_id": project_id,
                    "document_id": document_id,
                    "chunk_id": chunk["chunk_id"],
                    "chunk_index": chunk["chunk_index"],
                    "filename": filename,
                    "content": chunk["content"],
                },
            )
            for i, chunk in enumerate(chunks)
        ],
    )


def delete_document_vectors(document_id: str) -> None:
    _ensure_collection()
    _client.delete(
        collection_name=COLLECTION,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
            )
        ),
    )


def retrieve_chunks(client, project_id: str, query: str, top_k: int = 5) -> list[dict]:
    embedder = _ensure_collection()
    vector = next(iter(embedder.embed([query])))
    vector_hits = _client.query_points(
        collection_name=COLLECTION,
        query=vector.tolist(),
        query_filter=models.Filter(
            must=[models.FieldCondition(key="project_id", match=models.MatchValue(value=project_id))]
        ),
        limit=top_k,
    ).points

    merged: dict[str, dict] = {}
    for hit in vector_hits:
        if hit.score >= SCORE_THRESHOLD:
            merged[hit.payload["chunk_id"]] = {"score": hit.score, **hit.payload}

    keyword_rows = (
        client.table("document_chunks")
        .select("id, document_id, chunk_index, content, documents(filename)")
        .eq("project_id", project_id)
        .limit(top_k)
        .text_search("content_tsv", query, options={"type": "plain", "config": "english"})
        .execute()
        .data
    )
    for row in keyword_rows:
        if row["id"] not in merged:
            merged[row["id"]] = {
                "score": KEYWORD_MATCH_SCORE,
                "project_id": project_id,
                "document_id": row["document_id"],
                "chunk_id": row["id"],
                "chunk_index": row["chunk_index"],
                "filename": row["documents"]["filename"],
                "content": row["content"],
            }

    return sorted(merged.values(), key=lambda r: r["score"], reverse=True)[:top_k]
