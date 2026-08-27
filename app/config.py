from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, populated from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "keywords"

    # Embedding model
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embed_dim: int = 384

    # Metadata store
    database_url: str = "sqlite:///./simsearch.db"

    # Search defaults
    default_top_k: int = 10
    candidate_multiplier: int = 5
    min_candidates: int = 50

    # Hybrid score weights
    w_semantic: float = 0.5
    w_fuzzy: float = 0.4
    w_acronym: float = 0.1


@lru_cache
def get_settings() -> Settings:
    return Settings()
