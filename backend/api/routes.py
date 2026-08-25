"""API route handlers."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import (
    default_params,
    enrich_triggers,
    get_instrument_by_ticker,
    get_trigger_by_id,
    instrument_ids_for_asset_type,
    latest_market_date,
)
from backend.api.asset_pipelines import (
    data_status_for,
    refresh_crypto,
    refresh_stocks,
)
from backend.api.cron_auth import require_cron_secret
from backend.backtest.long_stats import summarize_long_performance
from backend.config import get_settings
from backend.db import get_supabase

router = APIRouter()


def _normalize_asset_type(asset_type: str | None) -> str | None:
    if asset_type is None:
        return None
    value = asset_type.upper()
    if value not in {"STOCK", "CRYPTO"}:
        raise HTTPException(status_code=400, detail="asset_type must be STOCK or CRYPTO")
    return value


def _filter_by_asset_type(
    query: Any, asset_type: str | None
) -> Any | None:
    """Return query filtered by instrument ids, or None if empty universe."""
    if not asset_type:
        return query
    ids = instrument_ids_for_asset_type(asset_type)
    if not ids:
        return None
    return query.in_("instrument_id", ids)


@router.get("/api/health")
def health() -> dict[str, str]:
    from backend import __version__

    return {
        "status": "ok",
        "service": "screamerscreener",
        "version": __version__,
    }


@router.get("/api/instruments")
def list_instruments(
    asset_type: str = Query(default="STOCK"),
) -> list[dict[str, Any]]:
    asset = _normalize_asset_type(asset_type) or "STOCK"
    client = get_supabase()
    query = (
        client.table("market_instruments")
        .select("*")
        .eq("active", True)
        .eq("asset_type", asset)
    )
    if asset == "CRYPTO":
        query = query.order("crypto_rank")
    else:
        query = query.order("ticker")
    return query.execute().data or []


@router.get("/api/stocks")
def list_stocks() -> list[dict[str, Any]]:
    """Backward-compatible: active STOCK instruments only."""
    return list_instruments(asset_type="STOCK")


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


@router.get("/api/stocks/{ticker}/secondary-indicators")
def get_secondary_indicators(
    ticker: str,
    limit: int = Query(default=400, ge=1, le=5000),
) -> dict[str, Any]:
    """Secondary indicators for a stock. Informational only — not used for triggers."""
    inst = get_instrument_by_ticker(ticker)
    if not inst:
        raise HTTPException(status_code=404, detail="Stock not found")
    client = get_supabase()
    rows = (
        client.table("secondary_indicator_values_daily")
        .select("*")
        .eq("instrument_id", inst["id"])
        .order("date", desc=True)
        .limit(limit)
        .execute()
    ).data or []
    series = list(reversed(rows))
    latest = series[-1] if series else None

    regime = None
    if latest:
        regime_rows = (
            client.table("market_regime_daily")
            .select("*")
            .eq("date", latest["date"])
            .limit(1)
            .execute()
        ).data or []
        regime = regime_rows[0] if regime_rows else None

    return {
        "ticker": ticker.upper(),
        "latest": latest,
        "series": series,
        "market_regime": regime,
        "note": "Secondary indicators are informational and do not generate or block triggers.",
    }


@router.get("/api/market-regime")
def get_market_regime(
    limit: int = Query(default=30, ge=1, le=500),
) -> list[dict[str, Any]]:
    client = get_supabase()
    rows = (
        client.table("market_regime_daily")
        .select("*")
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
def triggers_today(
    asset_type: str | None = Query(default=None),
) -> dict[str, Any]:
    asset = _normalize_asset_type(asset_type)
    # Default (no filter): STOCK only — keeps legacy dashboard stock-only
    scope = asset or "STOCK"
    market_date = latest_market_date(scope)
    if market_date is None:
        return {"date": None, "asset_type": scope, "long": [], "short": [], "stop": []}

    d_length, d_mult, d_source = default_params()
    client = get_supabase()
    query = (
        client.table("triggers_daily")
        .select("*")
        .eq("date", market_date.isoformat())
        .eq("length", d_length)
        .eq("mult", d_mult)
        .eq("source", d_source)
    )
    query = _filter_by_asset_type(query, scope)
    if query is None:
        return {
            "date": market_date.isoformat(),
            "asset_type": scope,
            "long": [],
            "short": [],
            "stop": [],
        }
    enriched = enrich_triggers(query.execute().data or [])
    return {
        "date": market_date.isoformat(),
        "asset_type": scope,
        "long": [t for t in enriched if t["trigger_type"] == "LONG"],
        "short": [t for t in enriched if t["trigger_type"] == "SHORT"],
        "stop": [t for t in enriched if t["trigger_type"] == "STOP"],
    }


@router.get("/api/triggers/week")
@router.get("/api/triggers/recent")
def triggers_recent(
    days: int = Query(default=30, ge=1, le=90),
    asset_type: str | None = Query(default=None),
) -> dict[str, Any]:
    """Last N trading days with triggers, newest first."""
    scope = _normalize_asset_type(asset_type) or "STOCK"
    market_date = latest_market_date(scope)
    if market_date is None:
        return {"from": None, "to": None, "asset_type": scope, "days": []}

    start = market_date - timedelta(days=days * 2 + 5)
    d_length, d_mult, d_source = default_params()
    client = get_supabase()
    query = (
        client.table("triggers_daily")
        .select("*")
        .gte("date", start.isoformat())
        .lte("date", market_date.isoformat())
        .eq("length", d_length)
        .eq("mult", d_mult)
        .eq("source", d_source)
        .order("date", desc=True)
    )
    query = _filter_by_asset_type(query, scope)
    rows = enrich_triggers(query.execute().data or []) if query is not None else []

    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_date.setdefault(row["date"], []).append(row)

    ids = instrument_ids_for_asset_type(scope)
    price_query = (
        client.table("market_prices_daily")
        .select("date")
        .lte("date", market_date.isoformat())
        .order("date", desc=True)
        .limit(max(days * 30, 200))
    )
    if ids:
        price_query = price_query.in_("instrument_id", ids)
    price_rows = price_query.execute().data or []

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
        "asset_type": scope,
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
    row = get_trigger_by_id(trigger_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return row


@router.get("/api/stats")
def stats(
    asset_type: str | None = Query(default=None),
) -> dict[str, Any]:
    scope = _normalize_asset_type(asset_type) or "STOCK"
    client = get_supabase()
    instruments = (
        client.table("market_instruments")
        .select("id", count="exact")
        .eq("active", True)
        .eq("asset_type", scope)
        .execute()
    )
    today = triggers_today(asset_type=scope)
    last = latest_market_date(scope)
    return {
        "asset_type": scope,
        "stocks": instruments.count or 0,
        "instruments": instruments.count or 0,
        "today": {
            "date": today["date"],
            "long": len(today["long"]),
            "short": len(today["short"]),
            "stop": len(today["stop"]),
        },
        "last_market_date": last.isoformat() if last else None,
    }


def _long_triggers(
    *,
    instrument_id: str | None = None,
    asset_type: str | None = "STOCK",
    limit: int = 5000,
) -> list[dict[str, Any]]:
    d_length, d_mult, d_source = default_params()
    client = get_supabase()
    query = (
        client.table("triggers_daily")
        .select("*")
        .eq("trigger_type", "LONG")
        .eq("length", d_length)
        .eq("mult", d_mult)
        .eq("source", d_source)
        .order("date", desc=True)
        .limit(limit)
    )
    if instrument_id:
        query = query.eq("instrument_id", instrument_id)
    elif asset_type:
        query = _filter_by_asset_type(query, asset_type.upper())
        if query is None:
            return []
    return enrich_triggers(query.execute().data or [])


@router.get("/api/stats/long-performance")
def long_performance_stats(
    asset_type: str | None = Query(default=None),
) -> dict[str, Any]:
    """Min / max / avg % after LONG signals at +5 / +10 / +15 trading days."""
    scope = _normalize_asset_type(asset_type) or "STOCK"
    rows = _long_triggers(asset_type=scope)
    summary = summarize_long_performance(rows)
    summary["asset_type"] = scope
    return summary


@router.get("/api/research/long-performance")
def research_long_performance(
    asset_type: str = Query(default="STOCK"),
) -> dict[str, Any]:
    """Research stats for a single universe (STOCK or CRYPTO — never mixed)."""
    return long_performance_stats(asset_type=asset_type)


@router.get("/api/stocks/{ticker}/long-stats")
def stock_long_stats(ticker: str) -> dict[str, Any]:
    inst = get_instrument_by_ticker(ticker)
    if not inst:
        raise HTTPException(status_code=404, detail="Stock not found")
    rows = _long_triggers(instrument_id=inst["id"], asset_type=None)
    summary = summarize_long_performance(rows)
    return {
        "ticker": ticker.upper(),
        "name": inst.get("name"),
        "asset_type": inst.get("asset_type"),
        "trigger_type": summary["trigger_type"],
        "long_count": summary["long_count"],
        "horizons": summary["horizons"],
        "note": summary["note"],
    }


@router.get("/api/crypto/overview")
def crypto_overview() -> dict[str, Any]:
    """TOP-N crypto table: price, vortex/trigger, secondary snapshot."""
    client = get_supabase()
    settings = get_settings()
    instruments = (
        client.table("market_instruments")
        .select("*")
        .eq("asset_type", "CRYPTO")
        .eq("active", True)
        .order("crypto_rank")
        .execute()
    ).data or []

    live_quotes: dict[str, dict[str, Any]] = {}
    provider_note = None
    if settings.freecryptoapi_api_key and instruments:
        try:
            from backend.data.freecryptoapi import FreeCryptoAPIProvider

            provider = FreeCryptoAPIProvider(max_requests=5)
            symbols = [
                (inst.get("api_symbol") or inst["ticker"]) for inst in instruments
            ]
            live_quotes = provider.get_latest_many(symbols)
        except Exception as exc:
            provider_note = str(exc)

    d_length, d_mult, d_source = default_params()
    rows_out: list[dict[str, Any]] = []
    for inst in instruments:
        iid = inst["id"]
        ticker = inst["ticker"]
        api_symbol = (inst.get("api_symbol") or ticker).upper()
        prices = (
            client.table("market_prices_daily")
            .select("date,close")
            .eq("instrument_id", iid)
            .order("date", desc=True)
            .limit(2)
            .execute()
        ).data or []
        price = float(prices[0]["close"]) if prices else None
        prev = float(prices[1]["close"]) if len(prices) > 1 else None
        change_24h = (
            (price / prev - 1.0) if price is not None and prev not in (None, 0) else None
        )
        live = live_quotes.get(api_symbol) or live_quotes.get(ticker.upper())
        if live:
            if live.get("price") is not None:
                price = float(live["price"])
            if live.get("change_24h") is not None:
                change_24h = float(live["change_24h"])

        ind = (
            client.table("indicator_values_daily")
            .select("date,basis,upper,lower")
            .eq("instrument_id", iid)
            .eq("length", d_length)
            .eq("mult", d_mult)
            .eq("source", d_source)
            .order("date", desc=True)
            .limit(1)
            .execute()
        ).data or []
        sec = (
            client.table("secondary_indicator_values_daily")
            .select("date,rsi14,adx14,relative_volume,ema20,ema50")
            .eq("instrument_id", iid)
            .order("date", desc=True)
            .limit(1)
            .execute()
        ).data or []
        trig = (
            client.table("triggers_daily")
            .select("id,date,trigger_type")
            .eq("instrument_id", iid)
            .eq("length", d_length)
            .eq("mult", d_mult)
            .eq("source", d_source)
            .order("date", desc=True)
            .limit(1)
            .execute()
        ).data or []

        latest_sec = sec[0] if sec else {}
        ema20 = latest_sec.get("ema20")
        ema50 = latest_sec.get("ema50")
        trend = None
        if ema20 is not None and ema50 is not None and price is not None:
            if price > float(ema20) > float(ema50):
                trend = "Bullish"
            elif price < float(ema20) < float(ema50):
                trend = "Bearish"
            else:
                trend = "Neutral"

        last_trig = trig[0] if trig else None
        # Same-day trigger if matches latest price date
        same_day_trigger = None
        if last_trig and prices and last_trig["date"] == prices[0]["date"]:
            same_day_trigger = last_trig["trigger_type"]

        rows_out.append(
            {
                "rank": inst.get("crypto_rank"),
                "ticker": inst["ticker"],
                "name": inst["name"],
                "in_top_universe": inst.get("in_top_universe", True),
                "price": price,
                "change_24h": change_24h,
                "vortex": ind[0] if ind else None,
                "trigger": same_day_trigger,
                "rsi14": latest_sec.get("rsi14"),
                "adx14": latest_sec.get("adx14"),
                "relative_volume": latest_sec.get("relative_volume"),
                "trend": trend,
                "last_trigger": last_trig,
            }
        )

    status = data_status_for("CRYPTO")
    instruments_with_prices = status.get("instruments_with_data") or 0
    note = provider_note
    if instruments_with_prices == 0:
        note = (
            (note + " · " if note else "")
            + "No daily candles yet. FreeCryptoAPI free plan blocks /getOHLC — "
            "run: python -m backend.ingestion.initial_load_crypto "
            "(uses Binance public daily as OHLC fallback)."
        )
    return {
        "top_n": settings.crypto_top_n,
        "last_data": status.get("last_daily_candle"),
        "last_refresh": status.get("last_refresh"),
        "rows": rows_out,
        "note": note,
        "live_quotes": len(live_quotes),
    }


@router.get("/api/data-status")
def data_status() -> dict[str, Any]:
    """Backward-compatible STOCK status (+ nested crypto for convenience)."""
    stocks = data_status_for("STOCK")
    crypto = data_status_for("CRYPTO")
    return {
        **stocks,
        "stocks": stocks,
        "crypto": crypto,
    }


@router.get("/api/data-status/stocks")
def data_status_stocks() -> dict[str, Any]:
    return data_status_for("STOCK")


@router.get("/api/data-status/crypto")
def data_status_crypto() -> dict[str, Any]:
    return data_status_for("CRYPTO")


@router.post("/api/refresh")
def refresh_data(_: None = Depends(require_cron_secret)) -> dict[str, Any]:
    """Alias for Refresh Stocks (EODHD only). Kept for compatibility."""
    try:
        return refresh_stocks()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/refresh/stocks")
def refresh_stocks_endpoint(_: None = Depends(require_cron_secret)) -> dict[str, Any]:
    try:
        return refresh_stocks()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/refresh/crypto")
def refresh_crypto_endpoint(_: None = Depends(require_cron_secret)) -> dict[str, Any]:
    try:
        return refresh_crypto()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
