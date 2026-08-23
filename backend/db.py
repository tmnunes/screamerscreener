"""Supabase client helpers (service role — backend only)."""

from functools import lru_cache

from supabase import Client, create_client

from backend.config import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env"
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
