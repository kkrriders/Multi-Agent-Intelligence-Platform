from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    groq_api_key: str
    groq_base_url: str | None = None  # override for AIRRA's mock-llm chaos scenario
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


settings = Settings()
