from collections.abc import Iterator

from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

_settings = get_settings()

# SQLite needs check_same_thread disabled for use across FastAPI's threadpool.
_url = make_url(_settings.database_url)
_connect_args = {"check_same_thread": False} if _url.get_backend_name() == "sqlite" else {}

engine = create_engine(_settings.database_url, echo=False, connect_args=_connect_args)


def init_db() -> None:
    """Create tables. Import models first so they register on SQLModel.metadata."""
    from app import models  # noqa: F401  (side-effect: registers tables)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped DB session."""
    with Session(engine) as session:
        yield session
