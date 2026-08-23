"""Shared ingestion helpers."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from backend.db import get_supabase

logger = logging.getLogger(__name__)


def list_active_instruments() -> list[dict[str, Any]]:
    client = get_supabase()
    result = (
        client.table("market_instruments")
        .select("*")
        .eq("active", True)
        .order("ticker")
        .execute()
    )
    return list(result.data or [])


def last_daily_date(instrument_id: str) -> date | None:
    client = get_supabase()
    result = (
        client.table("market_prices_daily")
        .select("date")
        .eq("instrument_id", instrument_id)
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return None
    return date.fromisoformat(rows[0]["date"])


def upsert_daily_prices(instrument_id: str, candles: list[dict[str, Any]]) -> int:
    if not candles:
        return 0
    client = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for c in candles:
        rows.append(
            {
                "instrument_id": instrument_id,
                "date": c["date"],
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
                "adjusted_close": c.get("adjusted_close"),
                "volume": c.get("volume"),
                "updated_at": now,
            }
        )

    # Upsert in chunks for safety
    chunk_size = 500
    total = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        client.table("market_prices_daily").upsert(
            chunk, on_conflict="instrument_id,date"
        ).execute()
        total += len(chunk)
    return total


def start_pipeline_run(run_type: str) -> str:
    client = get_supabase()
    result = (
        client.table("pipeline_runs")
        .insert({"run_type": run_type, "status": "started"})
        .execute()
    )
    return result.data[0]["id"]


def finish_pipeline_run(
    run_id: str,
    *,
    status: str,
    detail: dict[str, Any],
    api_requests_used: int,
) -> None:
    client = get_supabase()
    client.table("pipeline_runs").update(
        {
            "status": status,
            "detail": detail,
            "api_requests_used": api_requests_used,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", run_id).execute()


def next_day(d: date) -> date:
    return d + timedelta(days=1)
