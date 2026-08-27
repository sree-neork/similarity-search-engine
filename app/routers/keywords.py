from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app import embeddings, vector_store
from app.db import get_session
from app.models import Keyword, Namespace
from app.routers.namespaces import get_or_create_namespace
from app.schemas import KeywordCreate, KeywordRead, KeywordsAdded, KeywordUpdate

router = APIRouter(tags=["keywords"])


def _to_read(kw: Keyword) -> KeywordRead:
    return KeywordRead(
        id=kw.id,
        namespace_id=kw.namespace_id,
        text=kw.text,
        created_at=kw.created_at,
        updated_at=kw.updated_at,
    )


@router.post("/keywords", response_model=KeywordsAdded, status_code=201)
def add_keywords(body: KeywordCreate, session: Session = Depends(get_session)):
    """Add keyword(s) to a namespace given by name.

    If the namespace doesn't exist it is created and the keyword(s) added to it;
    if it already exists the keyword(s) are added directly to it.
    """
    texts = body.all_texts()
    if not texts:
        raise HTTPException(status_code=422, detail="No valid keyword text provided.")

    ns, created = get_or_create_namespace(session, body.namespace)

    keywords = [Keyword(namespace_id=ns.id, text=t) for t in texts]
    session.add_all(keywords)
    session.commit()
    for kw in keywords:
        session.refresh(kw)

    vectors = embeddings.embed_many([kw.text for kw in keywords])
    points = [
        vector_store.make_point(kw.id, ns.id, kw.text, vec)
        for kw, vec in zip(keywords, vectors)
    ]
    vector_store.upsert_batch(points)

    return KeywordsAdded(
        namespace=ns.name,
        namespace_id=ns.id,
        namespace_created=created,
        created=[_to_read(kw) for kw in keywords],
    )


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
