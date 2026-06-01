from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    All application configuration in one place.

    Field names are lowercase in Python but map to UPPERCASE env vars.
    e.g. settings.redis_url reads from the REDIS_URL environment variable.

    Fields with no default are REQUIRED. The app will not start without them.
    Fields with a default are OPTIONAL (have a reasonable fallback).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Don't crash if .env file doesn't exist (fine in production / CI)
        extra="ignore",
    )

    github_webhook_secret: str

    github_token: str

    github_api_base_url: str = "https://api.github.com"

    review_body_max_characters: int = 65536

    redis_url: str = "redis://localhost:6379/0"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pr_review_agent"

    qdrant_url: str = "http://localhost:6333"

    qdrant_collection_name: str = "codebase_embeddings"

    qdrant_api_key: str = ""

    openai_embedding_model: str = "text-embedding-3-small"

    openai_api_key: str

    anthropic_api_key: str

    app_env: str = "development"

    log_level: str = "INFO"

    max_concurrent_reviews: int = 3

    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    workflow_timeout_seconds: int = 300

    api_key: str = Field(default="", description="API key for the REST API. Required in production.")

    daily_budget_usd: float = Field(
        default=50.0,
        description="Hard daily LLM spend cap in USD. Agents short-circuit when exceeded.",
    )
    per_review_budget_usd: float = Field(
        default=0.50,
        description="Advisory per-review spend cap in USD. Surfaced as a metric, not enforced.",
    )

    @property
    def is_development(self) -> bool:
        """True when running locally. Enables Swagger UI, extra debug logging."""
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        """True in production. Disables debug features, enables strict error handling."""
        return self.app_env == "production"


@lru_cache()
def get_settings() -> Settings:
    """
    Returns the Settings singleton.

    lru_cache() means this function body runs exactly once.
    Every subsequent call returns the cached Settings object.
    This means we read from environment variables once at startup,
    not on every request.

    TWO WAYS TO USE THIS:

    1. As a FastAPI dependency (preferred for route handlers):

        from fastapi import Depends
        from backend.config.settings import get_settings, Settings

        @router.post("/webhook/github")
        async def my_endpoint(settings: Settings = Depends(get_settings)):
            secret = settings.github_webhook_secret

       This way tests can override settings without touching env vars:
        app.dependency_overrides[get_settings] = lambda: Settings(
            github_webhook_secret="test-secret",
            github_token="test-token",
            openai_api_key="test-key",
            anthropic_api_key="test-key",
        )

    2. For non-FastAPI code (background workers, job queue, CLI):

        from backend.config.settings import get_settings
        settings = get_settings()   # call explicitly, not at module import time

       This is fine because lru_cache ensures it only reads env vars once.
    """
    return Settings()