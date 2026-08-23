"""Shared API helpers / schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from backend.db import get_supabase
from backend.indicators.vortex_bands import DEFAULT_LENGTH, DEFAULT_MULT, DEFAULT_SOURCE


def default_params() -> tuple[int, float, str]:
    return DEFAULT_LENGTH, DEFAULT_MULT, DEFAULT_SOURCE


def get_instrument_by_ticker(ticker: str) -> dict[str, Any] | None:
    client = get_supabase()
    rows = (
        client.table("market_instruments")
        .select("*")
        .eq("ticker", ticker.upper())
        .limit(1)
        .execute()
    ).data or []
    return rows[0] if rows else None


def latest_market_date() -> date | None:
    client = get_supabase()
    rows = (
        client.table("market_prices_daily")
        .select("date")
        .order("date", desc=True)
        .limit(1)
        .execute()
    ).data or []
    if not rows:
        return None
    return date.fromisoformat(rows[0]["date"])


def latest_pipeline(run_type: str) -> dict[str, Any] | None:
    client = get_supabase()
    rows = (
        client.table("pipeline_runs")
        .select("*")
        .eq("run_type", run_type)
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    ).data or []
    return rows[0] if rows else None


def enrich_triggers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    client = get_supabase()
    instrument_ids = list({r["instrument_id"] for r in rows})
    instruments = (
        client.table("market_instruments")
        .select("id,ticker,name,exchange,country,currency")
        .in_("id", instrument_ids)
        .execute()
    ).data or []
    by_id = {i["id"]: i for i in instruments}

    trigger_ids = [r["id"] for r in rows]
    perfs = (
        client.table("trigger_performance")
        .select("*")
        .in_("trigger_id", trigger_ids)
        .execute()
    ).data or []
    perf_by_id = {p["trigger_id"]: p for p in perfs}

    out = []
    for row in rows:
        inst = by_id.get(row["instrument_id"], {})
        item = {
            **row,
            "ticker": inst.get("ticker"),
            "name": inst.get("name"),
            "exchange": inst.get("exchange"),
            "country": inst.get("country"),
            "currency": inst.get("currency"),
            "performance": perf_by_id.get(row["id"]),
        }
        out.append(item)
    return out


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)
