import os
import tempfile

import pytest

# Configure environment BEFORE importing app modules (settings read env at import).
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
os.environ.setdefault("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
os.environ.setdefault("EMBED_DIM", "384")

from fastapi.testclient import TestClient  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402

from app import vector_store  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _in_memory_qdrant():
    """Swap the Qdrant client for an in-memory local instance (no Docker needed)."""
    mem = QdrantClient(location=":memory:")
    vector_store._client.cache_clear()
    vector_store._client = lambda: mem  # type: ignore[assignment]
    yield


@pytest.fixture(scope="session")
def client(_in_memory_qdrant):
    with TestClient(app) as c:  # triggers lifespan: init_db, ensure_collection, warmup
        yield c


@pytest.fixture
def ns_name():
    """A fresh, unique namespace name per test (created implicitly on keyword add)."""
    import uuid

    return f"ns_{uuid.uuid4().hex[:8]}"
