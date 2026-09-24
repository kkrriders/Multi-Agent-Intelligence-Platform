from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    document_storage_dir: str = "./data/documents"
    groq_api_key: str
    groq_base_url: str | None = None  # override for AIRRA's mock-llm chaos scenario
    openrouter_api_key: str | None = None  # optional: orchestrator routing backup, see app/graph/routing.py
    qdrant_url: str = "http://qdrant:6333"

    # Phase 3 — Token Optimization
    cache_max_age_days: int = 7
    history_token_budget: int = 3000
    history_keep_turns: int = 3

    # Phase 3 — Production Hardening
    run_rate_limit_per_min: int = 20  # per authenticated user; 0 disables

    # Phase 3 — Deployment
    enable_deploy_api: bool = False  # gates the docker/git shell-out in POST /deployments

    class Config:
        env_file = ".env"
        extra = "ignore"  # shared root .env also carries frontend NEXT_PUBLIC_* vars


settings = Settings()  # pyright: ignore[reportCallIssue] — required fields come from env/.env at runtime

if len(settings.jwt_secret) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters")
