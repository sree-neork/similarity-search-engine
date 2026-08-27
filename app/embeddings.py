from functools import lru_cache

from fastembed import TextEmbedding

from app.config import get_settings


@lru_cache
def _model() -> TextEmbedding:
    settings = get_settings()
    return TextEmbedding(model_name=settings.embed_model)


def warmup() -> None:
    """Load the model (and run one encode) so the first request isn't slow."""
    embed_one("warmup")


def embed_one(text: str) -> list[float]:
    return embed_many([text])[0]


def embed_many(texts: list[str]) -> list[list[float]]:
    """Return one embedding vector per input text, order-preserved."""
    if not texts:
        return []
    vectors = list(_model().embed(texts))
    return [v.tolist() for v in vectors]
