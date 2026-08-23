"""Supabase client helpers (service role — backend only)."""

import httpx
from supabase import Client, ClientOptions, create_client

from backend.config import get_settings

_client: Client | None = None


def get_supabase() -> Client:
    """Return a shared Supabase client using HTTP/1.1 (avoids HTTP/2 stream limits)."""
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env"
        )

    httpx_client = httpx.Client(
        http2=False,
        timeout=httpx.Timeout(60.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    _client = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=ClientOptions(httpx_client=httpx_client),
    )
    return _client
