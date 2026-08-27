from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Namespace(SQLModel, table=True):
    """A group that holds keywords. Unique by name."""

    __tablename__ = "namespaces"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    keywords: list["Keyword"] = Relationship(
        back_populates="namespace",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Keyword(SQLModel, table=True):
    """A single keyword/phrase that belongs to a namespace."""

    __tablename__ = "keywords"

    id: Optional[int] = Field(default=None, primary_key=True)
    namespace_id: int = Field(foreign_key="namespaces.id", index=True)
    text: str = Field(index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    namespace: Optional[Namespace] = Relationship(back_populates="keywords")
