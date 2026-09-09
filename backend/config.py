from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ---- Storage ----
    data_dir: Path = Field(default=Path("./data"))

    # ---- Embedding ----
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # ---- Ingestion ----
    github_token: str | None = None
    num_repos_to_ingest: int = 200
    max_file_size_bytes: int = 200_000

    # ---- Search ----
    default_top_k: int = 10
    max_top_k: int = 50

    # ---- Server ----
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"


settings = Settings()

# Ensure data_dir exists so subsequent code can assume it.
settings.data_dir.mkdir(parents=True, exist_ok=True)
