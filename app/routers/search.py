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
    offset = req.offset
    w_sem = req.w_semantic if req.w_semantic is not None else settings.w_semantic
    w_fuz = req.w_fuzzy if req.w_fuzzy is not None else settings.w_fuzzy
    w_acr = req.w_acronym if req.w_acronym is not None else settings.w_acronym

    namespace_size = vector_store.count_namespace(ns.id)
    query_vec = embeddings.embed_one(req.q)

    # Two tiers by namespace size:
    #  - Tier 1 (small): score EVERY keyword -> exact total + exact ranking.
    #  - Tier 2 (large): score only a bounded cosine candidate pool that covers
    #    the requested page -> fast, but total/ranking are approximate. (When
    #    min_score is 0 every keyword matches, so the exact total is still known
    #    cheaply: it's the namespace size.)
    if namespace_size <= settings.exact_scan_limit:
        pool_limit = namespace_size
        exhaustive = True
    else:
        pool_limit = min(
            namespace_size,
            max((offset + top_k) * settings.candidate_multiplier, settings.min_candidates),
        )
        exhaustive = False

    candidates = vector_store.search(ns.id, query_vec, limit=pool_limit) if pool_limit else []

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

    if exhaustive:
        total, total_is_exact = len(scored), True
    elif req.min_score <= 0.0:
        # Every keyword passes at min_score=0 -> exact total without a full scan.
        total, total_is_exact = namespace_size, True
    else:
        # Approximate: only the retrieved pool was scored (lower bound).
        total, total_is_exact = len(scored), False

    page = scored[offset : offset + top_k]
    return SearchResponse(
        namespace=ns.name,
        query=req.q,
        count=len(page),
        total=total,
        total_is_exact=total_is_exact,
        offset=offset,
        limit=top_k,
        has_more=offset + top_k < total,
        results=page,
    )


@router.get("/search", response_model=SearchResponse)
def search_get(
    session: Session = Depends(get_session),
    namespace: str = Query(..., description="Namespace id or name"),
    q: str = Query(..., min_length=1, description="Query keyword"),
    top_k: Optional[int] = Query(None, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Results to skip (pagination)"),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    w_semantic: Optional[float] = Query(None, ge=0.0),
    w_fuzzy: Optional[float] = Query(None, ge=0.0),
    w_acronym: Optional[float] = Query(None, ge=0.0),
):
    req = SearchRequest(
        namespace=namespace,
        q=q,
        top_k=top_k,
        offset=offset,
        min_score=min_score,
        w_semantic=w_semantic,
        w_fuzzy=w_fuzzy,
        w_acronym=w_acronym,
    )
    return _run_search(req, session)


@router.post("/search", response_model=SearchResponse)
def search_post(req: SearchRequest, session: Session = Depends(get_session)):
    return _run_search(req, session)
