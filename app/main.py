from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlmodel import Session, select

from app import embeddings, vector_store
from app.db import get_session, init_db
from app.models import Keyword
from app.routers import keywords, namespaces, search


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: prepare metadata store, vector collection, and warm the model.
    init_db()
    vector_store.ensure_collection()
    embeddings.warmup()
    yield


app = FastAPI(
    title="Similarity Search Engine",
    description="Namespaced keyword similarity search (semantic + fuzzy + acronym).",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(namespaces.router)
app.include_router(keywords.router)
app.include_router(search.router)


@app.get("/health", tags=["ops"])
def health():
    qdrant_ok = vector_store.health()
    return {"status": "ok" if qdrant_ok else "degraded", "qdrant": qdrant_ok}


@app.post("/admin/reindex", tags=["ops"])
def reindex(session: Session = Depends(get_session)):
    """Rebuild all Qdrant vectors from the SQLite source of truth."""
    vector_store.ensure_collection()
    rows = session.exec(select(Keyword)).all()
    if not rows:
        return {"reindexed": 0}

    vectors = embeddings.embed_many([kw.text for kw in rows])
    points = [
        vector_store.make_point(kw.id, kw.namespace_id, kw.text, vec)
        for kw, vec in zip(rows, vectors)
    ]
    # Upsert in modest batches to keep payloads small.
    batch = 256
    for i in range(0, len(points), batch):
        vector_store.upsert_batch(points[i : i + batch])
    return {"reindexed": len(points)}
