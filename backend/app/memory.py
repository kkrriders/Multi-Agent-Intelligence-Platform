from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models

from app.config import settings

COLLECTION = "memory"
SCORE_THRESHOLD = 0.5
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

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


def history_to_messages(history: list[dict]) -> list[dict]:
    messages = []
    for run in history:
        messages.append({"role": "user", "content": run["input"]})
        messages.append({"role": "assistant", "content": run["output"]})
    return messages


def upsert_memory(run_id: str, project_id: str, conversation_id: str, input: str, output: str) -> None:
    embedder = _ensure_collection()
    document = f"User: {input}\nAssistant: {output}"
    vector = next(iter(embedder.embed([document])))
    _client.upsert(
        collection_name=COLLECTION,
        points=[
            models.PointStruct(
                id=run_id,
                vector=vector.tolist(),
                payload={
                    "project_id": project_id,
                    "conversation_id": conversation_id,
                    "run_id": run_id,
                    "input": input,
                    "output": output,
                },
            )
        ],
    )


def search_memory(project_id: str, query: str, top_k: int = 3) -> list[dict]:
    embedder = _ensure_collection()
    vector = next(iter(embedder.embed([query])))
    results = _client.query_points(
        collection_name=COLLECTION,
        query=vector.tolist(),
        query_filter=models.Filter(
            must=[models.FieldCondition(key="project_id", match=models.MatchValue(value=project_id))]
        ),
        limit=top_k,
    ).points
    return [{"score": r.score, **r.payload} for r in results if r.score >= SCORE_THRESHOLD]
