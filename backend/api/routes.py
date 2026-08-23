"""API route handlers."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.api.deps import (
    default_params,
    enrich_triggers,
    get_instrument_by_ticker,
    latest_market_date,
    latest_pipeline,
)
from backend.config import get_settings
from backend.db import get_supabase
from backend.indicators.calculate_daily import calculate_for_all
from backend.ingestion.sync_market_data import run_sync

router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, str]:
    from backend import __version__

    return {
        "status": "ok",
        "service": "screamerscreener",
        "version": __version__,
    }


@router.get("/api/stocks")
def list_stocks() -> list[dict[str, Any]]:
    client = get_supabase()
    return (
        client.table("market_instruments")
        .select("*")
        .eq("active", True)
        .order("ticker")
        .execute()
    ).data or []


@router.get("/api/stocks/{ticker}")
def get_stock(ticker: str) -> dict[str, Any]:
    inst = get_instrument_by_ticker(ticker)
    if not inst:
        raise HTTPException(status_code=404, detail="Stock not found")
    length, mult, source = default_params()
    return {
        **inst,
        "settings": {
            "length": length,
            "mult": mult,
            "source": source,
            "timeframe": "1D",
        },
    }


@router.get("/api/stocks/{ticker}/prices")
def get_prices(
    ticker: str,
    limit: int = Query(default=400, ge=1, le=5000),
) -> list[dict[str, Any]]:
    inst = get_instrument_by_ticker(ticker)
    if not inst:
        raise HTTPException(status_code=404, detail="Stock not found")
    client = get_supabase()
    rows = (
        client.table("market_prices_daily")
        .select("date,open,high,low,close,adjusted_close,volume")
        .eq("instrument_id", inst["id"])
        .order("date", desc=True)
        .limit(limit)
        .execute()
    ).data or []
    return list(reversed(rows))


@router.get("/api/stocks/{ticker}/indicators")
def get_indicators(
    ticker: str,
    length: int | None = None,
    mult: float | None = None,
    source: str | None = None,
    limit: int = Query(default=400, ge=1, le=5000),
) -> list[dict[str, Any]]:
    inst = get_instrument_by_ticker(ticker)
    if not inst:
        raise HTTPException(status_code=404, detail="Stock not found")
    d_length, d_mult, d_source = default_params()
    length = length if length is not None else d_length
    mult = mult if mult is not None else d_mult
    source = source if source is not None else d_source

    client = get_supabase()
    rows = (
        client.table("indicator_values_daily")
        .select("date,basis,upper,lower,length,mult,source")
        .eq("instrument_id", inst["id"])
        .eq("length", length)
        .eq("mult", mult)
        .eq("source", source)
        .order("date", desc=True)
        .limit(limit)
        .execute()
    ).data or []
    return list(reversed(rows))


@router.get("/api/stocks/{ticker}/triggers")
def get_stock_triggers(
    ticker: str,
    length: int | None = None,
    mult: float | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    inst = get_instrument_by_ticker(ticker)
    if not inst:
        raise HTTPException(status_code=404, detail="Stock not found")
    d_length, d_mult, d_source = default_params()
    length = length if length is not None else d_length
    mult = mult if mult is not None else d_mult
    source = source if source is not None else d_source

    client = get_supabase()
    rows = (
        client.table("triggers_daily")
        .select("*")
        .eq("instrument_id", inst["id"])
        .eq("length", length)
        .eq("mult", mult)
        .eq("source", source)
        .order("date", desc=True)
        .execute()
    ).data or []
    return enrich_triggers(rows)


@router.get("/api/triggers/today")
def triggers_today() -> dict[str, Any]:
    market_date = latest_market_date()
    if market_date is None:
        return {"date": None, "long": [], "short": [], "stop": []}

    d_length, d_mult, d_source = default_params()
    client = get_supabase()
    rows = (
        client.table("triggers_daily")
        .select("*")
        .eq("date", market_date.isoformat())
        .eq("length", d_length)
        .eq("mult", d_mult)
        .eq("source", d_source)
        .execute()
    ).data or []
    enriched = enrich_triggers(rows)
    return {
        "date": market_date.isoformat(),
        "long": [t for t in enriched if t["trigger_type"] == "LONG"],
        "short": [t for t in enriched if t["trigger_type"] == "SHORT"],
        "stop": [t for t in enriched if t["trigger_type"] == "STOP"],
    }


@router.get("/api/triggers/week")
@router.get("/api/triggers/recent")
def triggers_recent(days: int = Query(default=30, ge=1, le=90)) -> dict[str, Any]:
    """Last N trading days with triggers, newest first."""
    market_date = latest_market_date()
    if market_date is None:
        return {"from": None, "to": None, "days": []}

    # Calendar buffer so we still cover `days` trading sessions
    start = market_date - timedelta(days=days * 2 + 5)
    d_length, d_mult, d_source = default_params()
    client = get_supabase()
    rows = (
        client.table("triggers_daily")
        .select("*")
        .gte("date", start.isoformat())
        .lte("date", market_date.isoformat())
        .eq("length", d_length)
        .eq("mult", d_mult)
        .eq("source", d_source)
        .order("date", desc=True)
        .execute()
    ).data or []
    enriched = enrich_triggers(rows)

    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in enriched:
        by_date.setdefault(row["date"], []).append(row)

    price_rows = (
        client.table("market_prices_daily")
        .select("date")
        .lte("date", market_date.isoformat())
        .order("date", desc=True)
        .limit(max(days * 30, 200))
        .execute()
    ).data or []
    day_list = []
    seen: set[str] = set()
    for item in price_rows:
        d = item["date"]
        if d in seen:
            continue
        seen.add(d)
        day_triggers = by_date.get(d, [])
        day_list.append(
            {
                "date": d,
                "long": [t for t in day_triggers if t["trigger_type"] == "LONG"],
                "short": [t for t in day_triggers if t["trigger_type"] == "SHORT"],
                "stop": [t for t in day_triggers if t["trigger_type"] == "STOP"],
                "all": day_triggers,
            }
        )
        if len(day_list) >= days:
            break

    return {
        "from": day_list[-1]["date"] if day_list else None,
        "to": market_date.isoformat(),
        "days": day_list,
    }


@router.get("/api/triggers")
def list_triggers(
    trigger_type: str | None = None,
    country: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    d_length, d_mult, d_source = default_params()
    client = get_supabase()
    query = (
        client.table("triggers_daily")
        .select("*")
        .eq("length", d_length)
        .eq("mult", d_mult)
        .eq("source", d_source)
        .order("date", desc=True)
        .limit(limit)
    )
    if trigger_type:
        query = query.eq("trigger_type", trigger_type.upper())
    rows = enrich_triggers(query.execute().data or [])
    if country:
        country_l = country.lower()
        rows = [r for r in rows if (r.get("country") or "").lower() == country_l]
    return rows


@router.get("/api/triggers/{trigger_id}")
def get_trigger(trigger_id: str) -> dict[str, Any]:
    client = get_supabase()
    rows = (
        client.table("triggers_daily").select("*").eq("id", trigger_id).limit(1).execute()
    ).data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return enrich_triggers(rows)[0]


@router.get("/api/stats")
def stats() -> dict[str, Any]:
    client = get_supabase()
    instruments = (
        client.table("market_instruments")
        .select("id", count="exact")
        .eq("active", True)
        .execute()
    )
    today = triggers_today()
    return {
        "stocks": instruments.count or 0,
        "today": {
            "date": today["date"],
            "long": len(today["long"]),
            "short": len(today["short"]),
            "stop": len(today["stop"]),
        },
        "last_market_date": latest_market_date().isoformat()
        if latest_market_date()
        else None,
    }


@router.get("/api/data-status")
def data_status() -> dict[str, Any]:
    client = get_supabase()
    settings = get_settings()
    instruments = (
        client.table("market_instruments")
        .select("id", count="exact")
        .eq("active", True)
        .execute()
    )
    with_data = (
        client.table("market_prices_daily")
        .select("instrument_id")
        .execute()
    ).data or []
    unique_with_data = len({r["instrument_id"] for r in with_data})

    ingestion = latest_pipeline("ingestion")
    calculation = latest_pipeline("calculation")
    refresh = latest_pipeline("refresh")

    # Sum API requests from today's ingestion/refresh runs (best-effort)
    today_iso = date.today().isoformat()
    runs = (
        client.table("pipeline_runs")
        .select("api_requests_used,started_at")
        .gte("started_at", f"{today_iso}T00:00:00")
        .execute()
    ).data or []
    used_today = sum(int(r.get("api_requests_used") or 0) for r in runs)

    return {
        "last_daily_candle": latest_market_date().isoformat()
        if latest_market_date()
        else None,
        "last_ingestion": (ingestion or {}).get("finished_at")
        or (ingestion or {}).get("started_at"),
        "last_calculation": (calculation or {}).get("finished_at")
        or (calculation or {}).get("started_at"),
        "last_refresh": (refresh or {}).get("finished_at")
        or (refresh or {}).get("started_at"),
        "instruments": instruments.count or 0,
        "instruments_with_data": unique_with_data,
        "api_requests_used": used_today,
        "api_requests_limit": 20,
        "max_requests_per_run": settings.max_eodhd_requests_per_run,
    }


@router.post("/api/refresh")
def refresh_data() -> dict[str, Any]:
    """Manual refresh: sync market data then recalculate indicators/triggers."""
    from backend.ingestion.helpers import finish_pipeline_run, start_pipeline_run

    run_id = start_pipeline_run("refresh")
    try:
        sync_detail = run_sync()
        calc_detail = calculate_for_all()
        api_used = int(sync_detail.get("api_requests_used") or 0)
        detail = {"sync": sync_detail, "calculation": calc_detail}
        finish_pipeline_run(
            run_id,
            status="success",
            detail=detail,
            api_requests_used=api_used,
        )
        return {"status": "ok", "detail": detail}
    except Exception as exc:
        finish_pipeline_run(
            run_id,
            status="failed",
            detail={"error": str(exc)},
            api_requests_used=0,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
