from functools import lru_cache
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import get_settings


@lru_cache
def _client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection() -> None:
    """Create the single keyword collection if it doesn't exist yet."""
    settings = get_settings()
    client = _client()
    existing = {c.name for c in client.get_collections().collections}
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=qm.VectorParams(
                size=settings.embed_dim,
                distance=qm.Distance.COSINE,
            ),
        )
    # Index the namespace payload field so filtered search stays fast.
    try:
        client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="namespace_id",
            field_schema=qm.PayloadSchemaType.INTEGER,
        )
    except Exception:
        # Index already exists — Qdrant raises on duplicate creation.
        pass


def upsert_keyword(keyword_id: int, namespace_id: int, text: str, vector: list[float]) -> None:
    settings = get_settings()
    _client().upsert(
        collection_name=settings.qdrant_collection,
        points=[
            qm.PointStruct(
                id=keyword_id,
                vector=vector,
                payload={"namespace_id": namespace_id, "keyword_id": keyword_id, "text": text},
            )
        ],
    )


def upsert_batch(points: list[qm.PointStruct]) -> None:
    if not points:
        return
    settings = get_settings()
    _client().upsert(collection_name=settings.qdrant_collection, points=points)


def make_point(keyword_id: int, namespace_id: int, text: str, vector: list[float]) -> qm.PointStruct:
    return qm.PointStruct(
        id=keyword_id,
        vector=vector,
        payload={"namespace_id": namespace_id, "keyword_id": keyword_id, "text": text},
    )


def delete_keyword(keyword_id: int) -> None:
    settings = get_settings()
    _client().delete(
        collection_name=settings.qdrant_collection,
        points_selector=qm.PointIdsList(points=[keyword_id]),
    )


def delete_by_namespace(namespace_id: int) -> None:
    settings = get_settings()
    _client().delete(
        collection_name=settings.qdrant_collection,
        points_selector=qm.FilterSelector(
            filter=qm.Filter(
                must=[qm.FieldCondition(key="namespace_id", match=qm.MatchValue(value=namespace_id))]
            )
        ),
    )


def count_namespace(namespace_id: int) -> int:
    """Exact number of indexed keyword vectors in a namespace."""
    settings = get_settings()
    res = _client().count(
        collection_name=settings.qdrant_collection,
        count_filter=qm.Filter(
            must=[qm.FieldCondition(key="namespace_id", match=qm.MatchValue(value=namespace_id))]
        ),
        exact=True,
    )
    return res.count


def search(namespace_id: int, vector: list[float], limit: int) -> list[dict]:
    """Cosine search within a namespace. Returns [{keyword_id, text, score}]."""
    settings = get_settings()
    hits = _client().query_points(
        collection_name=settings.qdrant_collection,
        query=vector,
        query_filter=qm.Filter(
            must=[qm.FieldCondition(key="namespace_id", match=qm.MatchValue(value=namespace_id))]
        ),
        limit=limit,
        with_payload=True,
    ).points
    results = []
    for h in hits:
        payload = h.payload or {}
        results.append(
            {
                "keyword_id": payload.get("keyword_id", h.id),
                "text": payload.get("text", ""),
                "score": float(h.score),  # cosine similarity in [-1, 1], typically [0, 1]
            }
        )
    return results


def health() -> bool:
    try:
        _client().get_collections()
        return True
    except Exception:
        return False
