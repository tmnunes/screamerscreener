"""Shared API helpers / schemas."""

from __future__ import annotations

from datetime import date
from typing import Any

from backend.backtest.performance import (
    future_trading_days_available,
    performance_as_dict,
    performance_from_price_series,
    performance_needs_update,
    performance_to_row,
    HORIZON_OFFSETS,
)
from backend.db import get_supabase
from backend.indicators.secondary_signals import evaluate_secondary_signals
from backend.indicators.vortex_bands import DEFAULT_LENGTH, DEFAULT_MULT, DEFAULT_SOURCE

TRIGGER_SELECT = (
    "*, market_instruments(ticker,name,exchange,country,currency), "
    "trigger_performance(*)"
)


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


def _unwrap_one(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    if isinstance(value, dict):
        return value
    return None


def flatten_trigger_row(row: dict[str, Any]) -> dict[str, Any]:
    inst = _unwrap_one(row.pop("market_instruments", None)) or {}
    perf = _unwrap_one(row.pop("trigger_performance", None))
    return {
        **row,
        "ticker": inst.get("ticker"),
        "name": inst.get("name"),
        "exchange": inst.get("exchange"),
        "country": inst.get("country"),
        "currency": inst.get("currency"),
        "performance": perf,
    }


def _fetch_prices_for_instrument(instrument_id: str) -> list[dict[str, Any]]:
    client = get_supabase()
    return (
        client.table("market_prices_daily")
        .select("date,close")
        .eq("instrument_id", instrument_id)
        .order("date")
        .execute()
    ).data or []


def _fetch_secondary_map(
    triggers: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    if not triggers:
        return {}
    client = get_supabase()
    instrument_ids = list({t["instrument_id"] for t in triggers})
    dates = list({t["date"] for t in triggers})
    rows = (
        client.table("secondary_indicator_values_daily")
        .select("*")
        .in_("instrument_id", instrument_ids)
        .in_("date", dates)
        .execute()
    ).data or []
    return {(r["instrument_id"], r["date"]): r for r in rows}


def _fetch_regime_map(dates: list[str]) -> dict[str, dict[str, Any]]:
    if not dates:
        return {}
    client = get_supabase()
    rows = (
        client.table("market_regime_daily")
        .select("*")
        .in_("date", dates)
        .execute()
    ).data or []
    return {r["date"]: r for r in rows}


def _attach_secondary_signals(
    trigger: dict[str, Any],
    secondary_map: dict[tuple[str, str], dict[str, Any]],
    regime_map: dict[str, dict[str, Any]],
) -> None:
    key = (trigger["instrument_id"], trigger["date"])
    summary = evaluate_secondary_signals(
        trigger_type=trigger["trigger_type"],
        trigger_price=float(trigger["trigger_price"]),
        secondary_row=secondary_map.get(key),
        market_regime=regime_map.get(trigger["date"]),
    )
    trigger["secondary_signals"] = summary.as_dict() if summary else None


def _refresh_performance(
    triggers: list[dict[str, Any]], *, force: bool = False
) -> None:
    """Compute and persist performance using the latest stored daily prices."""
    if not triggers:
        return

    by_instrument: dict[str, list[dict[str, Any]]] = {}
    for trigger in triggers:
        by_instrument.setdefault(trigger["instrument_id"], []).append(trigger)

    upsert_rows: list[dict[str, Any]] = []
    for instrument_id, inst_triggers in by_instrument.items():
        prices = _fetch_prices_for_instrument(instrument_id)
        if not prices:
            continue
        for trigger in inst_triggers:
            future_days = future_trading_days_available(prices, trigger["date"])
            if not force and not performance_needs_update(
                trigger.get("performance"), future_days
            ):
                continue
            perf = performance_from_price_series(
                prices,
                trigger_date=trigger["date"],
                trigger_type=trigger["trigger_type"],
                trigger_price=float(trigger["trigger_price"]),
            )
            trigger["performance"] = performance_as_dict(perf)
            upsert_rows.append(performance_to_row(trigger["id"], perf))

    if not upsert_rows:
        return

    client = get_supabase()
    chunk_size = 200
    for i in range(0, len(upsert_rows), chunk_size):
        client.table("trigger_performance").upsert(
            upsert_rows[i : i + chunk_size],
            on_conflict="trigger_id",
        ).execute()


def enrich_triggers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    trigger_ids = [r["id"] for r in rows]
    client = get_supabase()

    try:
        enriched = (
            client.table("triggers_daily")
            .select(TRIGGER_SELECT)
            .in_("id", trigger_ids)
            .execute()
        ).data or []
        flat_rows = [flatten_trigger_row(dict(item)) for item in enriched]
    except Exception:
        # Fallback if nested embed is unavailable
        instruments = (
            client.table("market_instruments")
            .select("id,ticker,name,exchange,country,currency")
            .execute()
        ).data or []
        inst_by_id = {i["id"]: i for i in instruments}
        perfs = (
            client.table("trigger_performance")
            .select("*")
            .in_("trigger_id", trigger_ids)
            .execute()
        ).data or []
        perf_by_id = {p["trigger_id"]: p for p in perfs}
        flat_rows = []
        for row in rows:
            inst = inst_by_id.get(row["instrument_id"], {})
            flat_rows.append(
                {
                    **row,
                    "ticker": inst.get("ticker"),
                    "name": inst.get("name"),
                    "exchange": inst.get("exchange"),
                    "country": inst.get("country"),
                    "currency": inst.get("currency"),
                    "performance": perf_by_id.get(row["id"]),
                }
            )

    _refresh_performance(flat_rows)
    secondary_map = _fetch_secondary_map(flat_rows)
    regime_map = _fetch_regime_map(list({t["date"] for t in flat_rows}))
    for item in flat_rows:
        _attach_secondary_signals(item, secondary_map, regime_map)
    by_id = {item["id"]: item for item in flat_rows}
    return [by_id.get(r["id"], {**r, "performance": None}) for r in rows]


def _attach_performance_meta(
    trigger: dict[str, Any], prices: list[dict[str, Any]]
) -> None:
    future = future_trading_days_available(prices, trigger["date"])
    date_to_idx = {p["date"]: i for i, p in enumerate(prices)}
    idx = date_to_idx.get(trigger["date"])

    horizon_dates: dict[str, str | None] = {}
    if idx is not None:
        for offset in HORIZON_OFFSETS:
            target_idx = idx + offset
            key = f"{offset}d"
            horizon_dates[key] = (
                prices[target_idx]["date"] if target_idx < len(prices) else None
            )

    trigger["performance_meta"] = {
        "future_trading_days": future,
        "last_market_date": prices[-1]["date"] if prices else None,
        "horizons": {
            f"{offset}d": future >= offset for offset in HORIZON_OFFSETS
        },
        "horizon_dates": horizon_dates,
    }


def get_trigger_by_id(trigger_id: str) -> dict[str, Any] | None:
    client = get_supabase()
    rows = (
        client.table("triggers_daily")
        .select(TRIGGER_SELECT)
        .eq("id", trigger_id)
        .limit(1)
        .execute()
    ).data or []
    if not rows:
        return None
    flat = flatten_trigger_row(dict(rows[0]))
    prices = _fetch_prices_for_instrument(flat["instrument_id"])
    _refresh_performance([flat], force=True)
    _attach_performance_meta(flat, prices)
    secondary_map = _fetch_secondary_map([flat])
    regime_map = _fetch_regime_map([flat["date"]])
    _attach_secondary_signals(flat, secondary_map, regime_map)
    return flat


def parse_iso_date(value: str | None) -> date | None:
    if value:
        return date.fromisoformat(value)
    return None
