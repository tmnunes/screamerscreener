"""Auth helper for scheduled refresh endpoints."""

from __future__ import annotations

from fastapi import Header, HTTPException

from backend.config import get_settings


def require_cron_secret(
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
    authorization: str | None = Header(default=None),
) -> None:
    """If CRON_SECRET is configured, require it on refresh calls.

    Accepts:
      X-Cron-Secret: <secret>
      Authorization: Bearer <secret>
    """
    expected = (get_settings().cron_secret or "").strip()
    if not expected:
        return

    bearer = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()

    provided = (x_cron_secret or bearer or "").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing cron secret")
