"""Settings loaded from environment + .env file."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    eniak_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./data/eniak.sqlite3"
    eniak_cors_origins: str = "https://www.eniak.org,https://eniak.org,http://localhost:3000"
    eniak_default_model: str = "qwen3.5-plus"
    llm_api_key: str | None = None
    llm_base_url: str = "https://coding.dashscope.aliyuncs.com/v1"
    # Optional fallback creds, surfaced for the /config snapshot.
    kimi_coding_api_key: str | None = None
    dashscope_api_key: str | None = None
    eniak_llm_debug: bool = False

    # Optional, currently unused but reserved so .env stays in sync.
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    eniak_storage_dir: str = Field(default="./storage")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.eniak_cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
