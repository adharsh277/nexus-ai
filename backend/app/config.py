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

    # --- Reminder & Scheduler Settings ---
    reminder_poll_interval_seconds: float = 10.0

    # --- Document & Storage Settings ---
    document_storage_dir: str = "/app/storage/documents"
    document_max_file_size_bytes: int = 20 * 1024 * 1024  # 20 MB
    document_chunk_size: int = 1000
    document_chunk_overlap: int = 200

    # --- Embedding Settings ---
    embedding_provider: str = "gemini"
    embedding_model: str = "text-embedding-004"
    embedding_dimensions: int = 768
    ollama_base_url: str = "http://localhost:11434"
    ollama_embedding_model: str = "nomic-embed-text"

    def get_storage_path(self) -> "Path":
        from pathlib import Path
        target = Path(self.document_storage_dir)
        try:
            target.mkdir(parents=True, exist_ok=True)
            test_file = target / ".write_test"
            test_file.touch()
            test_file.unlink()
            return target
        except Exception:
            local_fallback = Path(__file__).resolve().parents[1] / "storage" / "documents"
            local_fallback.mkdir(parents=True, exist_ok=True)
            return local_fallback



@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
