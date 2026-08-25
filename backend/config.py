"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    eodhd_api_key: str = ""
    max_eodhd_requests_per_run: int = 18

    freecryptoapi_api_key: str = ""
    max_freecryptoapi_requests_per_run: int = 40
    crypto_top_n: int = 25
    crypto_history_days: int = 730

    supabase_url: str = ""
    supabase_service_role_key: str = ""

    vortex_length: int = 47
    vortex_mult: float = 1.6
    vortex_source: str = "hlc3"

    # Optional. If set, POST /api/refresh* require header X-Cron-Secret.
    cron_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
