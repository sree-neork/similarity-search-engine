from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app import embeddings, vector_store
from app.db import get_session
from app.models import Keyword, Namespace
from app.schemas import KeywordCreate, KeywordRead, KeywordUpdate

router = APIRouter(tags=["keywords"])


def _to_read(kw: Keyword) -> KeywordRead:
    return KeywordRead(
        id=kw.id,
        namespace_id=kw.namespace_id,
        text=kw.text,
        created_at=kw.created_at,
        updated_at=kw.updated_at,
    )


@router.post("/namespaces/{namespace_id}/keywords", response_model=list[KeywordRead], status_code=201)
def add_keywords(
    namespace_id: int, body: KeywordCreate, session: Session = Depends(get_session)
):
    ns = session.get(Namespace, namespace_id)
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found.")

    texts = body.all_texts()
    if not texts:
        raise HTTPException(status_code=422, detail="No valid keyword text provided.")

    keywords = [Keyword(namespace_id=namespace_id, text=t) for t in texts]
    session.add_all(keywords)
    session.commit()
    for kw in keywords:
        session.refresh(kw)

    vectors = embeddings.embed_many([kw.text for kw in keywords])
    points = [
        vector_store.make_point(kw.id, namespace_id, kw.text, vec)
        for kw, vec in zip(keywords, vectors)
    ]
    vector_store.upsert_batch(points)

    return [_to_read(kw) for kw in keywords]


@router.get("/namespaces/{namespace_id}/keywords", response_model=list[KeywordRead])
def list_keywords(
    namespace_id: int,
    session: Session = Depends(get_session),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    ns = session.get(Namespace, namespace_id)
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found.")
    rows = session.exec(
        select(Keyword)
        .where(Keyword.namespace_id == namespace_id)
        .order_by(Keyword.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return [_to_read(kw) for kw in rows]


@router.get("/keywords/{keyword_id}", response_model=KeywordRead)
def get_keyword(keyword_id: int, session: Session = Depends(get_session)):
    kw = session.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found.")
    return _to_read(kw)


@router.put("/keywords/{keyword_id}", response_model=KeywordRead)
def update_keyword(keyword_id: int, body: KeywordUpdate, session: Session = Depends(get_session)):
    kw = session.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found.")
    kw.text = body.text.strip()
    kw.updated_at = datetime.now(timezone.utc)
    session.add(kw)
    session.commit()
    session.refresh(kw)

    vector = embeddings.embed_one(kw.text)
    vector_store.upsert_keyword(kw.id, kw.namespace_id, kw.text, vector)
    return _to_read(kw)


@router.delete("/keywords/{keyword_id}", status_code=204)
def delete_keyword(keyword_id: int, session: Session = Depends(get_session)):
    kw = session.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found.")
    session.delete(kw)
    session.commit()
    vector_store.delete_keyword(keyword_id)
    return None
