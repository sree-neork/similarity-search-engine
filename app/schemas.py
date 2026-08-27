from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ---------- Namespaces ----------
class NamespaceRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    keyword_count: int = 0
    created_at: datetime
    updated_at: datetime


# ---------- Keywords ----------
class KeywordCreate(BaseModel):
    """Add keyword(s) to a namespace (by name).

    The namespace is resolved by name and created automatically if it does not
    exist yet; if it already exists the keyword(s) are added to it directly.
    Accepts a single `text` or a bulk `texts` list (at least one required).
    """

    namespace: str = Field(
        min_length=1, max_length=200, description="Namespace name; created if it doesn't exist"
    )
    text: Optional[str] = Field(default=None, min_length=1, max_length=500)
    texts: Optional[list[str]] = None

    @model_validator(mode="after")
    def _require_one(self) -> "KeywordCreate":
        if not self.text and not self.texts:
            raise ValueError("Provide either 'text' or a non-empty 'texts' list.")
        if self.texts is not None and len(self.texts) == 0:
            raise ValueError("'texts' must not be empty.")
        return self

    def all_texts(self) -> list[str]:
        items = list(self.texts) if self.texts else []
        if self.text:
            items.append(self.text)
        # de-dupe while preserving order, drop blanks
        seen: set[str] = set()
        out: list[str] = []
        for t in items:
            t = t.strip()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out


class KeywordUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class KeywordRead(BaseModel):
    id: int
    namespace_id: int
    text: str
    created_at: datetime
    updated_at: datetime


class KeywordsAdded(BaseModel):
    """Result of adding keyword(s): reports the resolved namespace + created keywords."""

    namespace: str
    namespace_id: int
    namespace_created: bool
    created: list[KeywordRead]


# ---------- Search ----------
class SearchRequest(BaseModel):
    namespace: str = Field(description="Namespace id or name")
    q: str = Field(min_length=1, description="Query keyword")
    top_k: Optional[int] = Field(default=None, ge=1, le=100, description="Page size")
    offset: int = Field(default=0, ge=0, description="Number of leading results to skip (pagination)")
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    w_semantic: Optional[float] = Field(default=None, ge=0.0)
    w_fuzzy: Optional[float] = Field(default=None, ge=0.0)
    w_acronym: Optional[float] = Field(default=None, ge=0.0)


class SearchHit(BaseModel):
    keyword_id: int
    text: str
    score: float
    semantic_score: float
    fuzzy_score: float
    acronym_match: bool


class SearchResponse(BaseModel):
    namespace: str
    query: str
    count: int  # number of hits on this page
    total: int  # total matching keywords (see total_is_exact)
    total_is_exact: bool  # False only for large namespaces scored via a bounded pool
    offset: int
    limit: int  # page size (top_k)
    has_more: bool
    results: list[SearchHit]
