from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from environment variables (and an optional .env file)."""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://nexus:nexus@localhost:5432/nexus"
    test_database_url: str = "postgresql+psycopg://nexus:nexus@localhost:5432/nexus_test"
    frontend_origin: str = "http://localhost:5173"
    log_level: str = "INFO"
    default_user_email: str = "local@nexus.ai"
    default_user_name: str = "Local User"

    # --- AI & LLM Settings ---
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    llm_timeout_seconds: float = 30.0
    llm_max_history_messages: int = 20
    llm_temperature: float = 0.7
    llm_max_output_tokens: int = 2048


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
