"""Market regime helpers (SPY / QQQ vs SMA200). Informational only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.db import get_supabase
from backend.indicators.series_math import sma_series


def _prices_for_ticker(ticker: str) -> list[dict[str, Any]]:
    client = get_supabase()
    inst = (
        client.table("market_instruments")
        .select("id")
        .eq("ticker", ticker.upper())
        .limit(1)
        .execute()
    ).data
    if not inst:
        return []
    return (
        client.table("market_prices_daily")
        .select("date,close")
        .eq("instrument_id", inst[0]["id"])
        .order("date")
        .execute()
    ).data or []


def upsert_market_regime() -> int:
    """Build market_regime_daily from SPY/QQQ if those instruments have price data.

    Does not call EODHD. Returns number of rows upserted.
    """
    spy = _prices_for_ticker("SPY")
    qqq = _prices_for_ticker("QQQ")
    if not spy and not qqq:
        return 0

    spy_by_date = {p["date"]: float(p["close"]) for p in spy}
    qqq_by_date = {p["date"]: float(p["close"]) for p in qqq}

    spy_closes = [float(p["close"]) for p in spy]
    qqq_closes = [float(p["close"]) for p in qqq]
    spy_sma = sma_series(spy_closes, 200) if spy else []
    qqq_sma = sma_series(qqq_closes, 200) if qqq else []
    spy_sma_by_date = {p["date"]: spy_sma[i] for i, p in enumerate(spy)} if spy else {}
    qqq_sma_by_date = {p["date"]: qqq_sma[i] for i, p in enumerate(qqq)} if qqq else {}

    all_dates = sorted(set(spy_by_date) | set(qqq_by_date))
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for d in all_dates:
        spy_c = spy_by_date.get(d)
        qqq_c = qqq_by_date.get(d)
        spy_s = spy_sma_by_date.get(d)
        qqq_s = qqq_sma_by_date.get(d)
        rows.append(
            {
                "date": d,
                "spy_close": spy_c,
                "spy_sma200": spy_s,
                "spy_above_sma200": (
                    None if spy_c is None or spy_s is None else spy_c > spy_s
                ),
                "qqq_close": qqq_c,
                "qqq_sma200": qqq_s,
                "qqq_above_sma200": (
                    None if qqq_c is None or qqq_s is None else qqq_c > qqq_s
                ),
                "vix_close": None,  # reserved — not ingested in this phase
                "updated_at": now,
            }
        )

    client = get_supabase()
    chunk = 500
    for i in range(0, len(rows), chunk):
        client.table("market_regime_daily").upsert(
            rows[i : i + chunk], on_conflict="date"
        ).execute()
    return len(rows)
