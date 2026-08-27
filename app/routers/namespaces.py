from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app import vector_store
from app.db import get_session
from app.models import Keyword, Namespace
from app.schemas import NamespaceRead, NamespaceUpdate

router = APIRouter(prefix="/namespaces", tags=["namespaces"])


def _to_read(session: Session, ns: Namespace) -> NamespaceRead:
    count = session.exec(
        select(func.count()).select_from(Keyword).where(Keyword.namespace_id == ns.id)
    ).one()
    return NamespaceRead(
        id=ns.id,
        name=ns.name,
        description=ns.description,
        keyword_count=count,
        created_at=ns.created_at,
        updated_at=ns.updated_at,
    )


def get_or_create_namespace(session: Session, name: str) -> tuple[Namespace, bool]:
    """Fetch a namespace by name, creating it if it doesn't exist.

    Returns (namespace, created) where `created` is True only when a new
    namespace was inserted. Namespaces are created implicitly when keywords are
    added, so there is no standalone create endpoint.
    """
    name = name.strip()
    ns = session.exec(select(Namespace).where(Namespace.name == name)).first()
    if ns:
        return ns, False

    ns = Namespace(name=name)
    session.add(ns)
    try:
        session.commit()
    except IntegrityError:
        # Lost a race with a concurrent insert — fetch the existing row.
        session.rollback()
        ns = session.exec(select(Namespace).where(Namespace.name == name)).first()
        if ns is None:
            raise
        return ns, False
    session.refresh(ns)
    return ns, True


@router.get("", response_model=list[NamespaceRead])
def list_namespaces(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    rows = session.exec(select(Namespace).order_by(Namespace.id).offset(offset).limit(limit)).all()
    return [_to_read(session, ns) for ns in rows]


@router.get("/{namespace_id}", response_model=NamespaceRead)
def get_namespace(namespace_id: int, session: Session = Depends(get_session)):
    ns = session.get(Namespace, namespace_id)
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found.")
    return _to_read(session, ns)


@router.put("/{namespace_id}", response_model=NamespaceRead)
def update_namespace(
    namespace_id: int, body: NamespaceUpdate, session: Session = Depends(get_session)
):
    ns = session.get(Namespace, namespace_id)
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found.")
    if body.name is not None:
        ns.name = body.name.strip()
    if body.description is not None:
        ns.description = body.description
    ns.updated_at = datetime.now(timezone.utc)
    session.add(ns)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=f"Namespace '{body.name}' already exists.")
    session.refresh(ns)
    return _to_read(session, ns)


@router.delete("/{namespace_id}", status_code=204)
def delete_namespace(namespace_id: int, session: Session = Depends(get_session)):
    ns = session.get(Namespace, namespace_id)
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found.")
    session.delete(ns)  # cascade removes keywords in SQLite
    session.commit()
    vector_store.delete_by_namespace(namespace_id)
    return None
