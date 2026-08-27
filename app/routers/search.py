from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app import embeddings, scoring, vector_store
from app.config import get_settings
from app.db import get_session
from app.models import Namespace
from app.schemas import SearchHit, SearchRequest, SearchResponse

router = APIRouter(tags=["search"])


def _resolve_namespace(session: Session, namespace: str) -> Namespace:
    """Accept either a numeric id or a namespace name."""
    ns: Optional[Namespace] = None
    if namespace.isdigit():
        ns = session.get(Namespace, int(namespace))
    if ns is None:
        ns = session.exec(select(Namespace).where(Namespace.name == namespace)).first()
    if ns is None:
        raise HTTPException(status_code=404, detail=f"Namespace '{namespace}' not found.")
    return ns


def _run_search(req: SearchRequest, session: Session) -> SearchResponse:
    settings = get_settings()
    ns = _resolve_namespace(session, req.namespace)

    top_k = req.top_k or settings.default_top_k
    w_sem = req.w_semantic if req.w_semantic is not None else settings.w_semantic
    w_fuz = req.w_fuzzy if req.w_fuzzy is not None else settings.w_fuzzy
    w_acr = req.w_acronym if req.w_acronym is not None else settings.w_acronym

    # Pull a wider candidate pool so fuzzy/acronym can promote items the
    # pure vector search ranked lower (e.g. heavy misspellings).
    pool = max(top_k * settings.candidate_multiplier, settings.min_candidates)

    query_vec = embeddings.embed_one(req.q)
    candidates = vector_store.search(ns.id, query_vec, limit=pool)

    scored: list[SearchHit] = []
    for c in candidates:
        s = scoring.hybrid_score(
            query=req.q,
            text=c["text"],
            semantic=c["score"],
            w_semantic=w_sem,
            w_fuzzy=w_fuz,
            w_acronym=w_acr,
        )
        if s["score"] < req.min_score:
            continue
        scored.append(
            SearchHit(
                keyword_id=c["keyword_id"],
                text=c["text"],
                score=round(s["score"], 6),
                semantic_score=round(s["semantic_score"], 6),
                fuzzy_score=round(s["fuzzy_score"], 6),
                acronym_match=s["acronym_match"],
            )
        )

    scored.sort(key=lambda h: h.score, reverse=True)
    top = scored[:top_k]
    return SearchResponse(namespace=ns.name, query=req.q, count=len(top), results=top)


@router.get("/search", response_model=SearchResponse)
def search_get(
    session: Session = Depends(get_session),
    namespace: str = Query(..., description="Namespace id or name"),
    q: str = Query(..., min_length=1, description="Query keyword"),
    top_k: Optional[int] = Query(None, ge=1, le=100),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    w_semantic: Optional[float] = Query(None, ge=0.0),
    w_fuzzy: Optional[float] = Query(None, ge=0.0),
    w_acronym: Optional[float] = Query(None, ge=0.0),
):
    req = SearchRequest(
        namespace=namespace,
        q=q,
        top_k=top_k,
        min_score=min_score,
        w_semantic=w_semantic,
        w_fuzzy=w_fuzzy,
        w_acronym=w_acronym,
    )
    return _run_search(req, session)


@router.post("/search", response_model=SearchResponse)
def search_post(req: SearchRequest, session: Session = Depends(get_session)):
    return _run_search(req, session)
