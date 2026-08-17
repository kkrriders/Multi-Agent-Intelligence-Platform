from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    groq_api_key: str
    qdrant_url: str = "http://qdrant:6333"

    class Config:
        env_file = ".env"


settings = Settings()
