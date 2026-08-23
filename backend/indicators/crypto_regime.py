"""Crypto market regime helpers (BTC benchmark). Informational only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.db import get_supabase
from backend.indicators.series_math import rsi_series, sma_series


def _btc_prices() -> list[dict[str, Any]]:
    client = get_supabase()
    inst = (
        client.table("market_instruments")
        .select("id")
        .eq("ticker", "BTC")
        .eq("asset_type", "CRYPTO")
        .limit(1)
        .execute()
    ).data
    if not inst:
        # fallback: any BTC ticker
        inst = (
            client.table("market_instruments")
            .select("id")
            .eq("ticker", "BTC")
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


def _trend_label(
    *,
    above_50: bool | None,
    above_200: bool | None,
    rsi: float | None,
) -> str | None:
    if above_50 is None and above_200 is None:
        return None
    bullish = (above_50 is True) and (above_200 is not False)
    bearish = (above_50 is False) and (above_200 is not True)
    if bullish and (rsi is None or rsi >= 45):
        return "bullish"
    if bearish and (rsi is None or rsi <= 55):
        return "bearish"
    return "neutral"


def upsert_crypto_market_regime() -> int:
    """Build crypto_market_regime_daily from BTC prices. No FreeCryptoAPI calls."""
    btc = _btc_prices()
    if not btc:
        return 0

    closes = [float(p["close"]) for p in btc]
    sma50 = sma_series(closes, 50)
    sma200 = sma_series(closes, 200)
    rsi14 = rsi_series(closes, 14)

    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for i, p in enumerate(btc):
        close = closes[i]
        s50 = sma50[i]
        s200 = sma200[i]
        rsi = rsi14[i]
        above_50 = None if s50 is None else close > s50
        above_200 = None if s200 is None else close > s200
        rows.append(
            {
                "date": p["date"],
                "btc_close": close,
                "btc_sma50": s50,
                "btc_sma200": s200,
                "btc_above_sma50": above_50,
                "btc_above_sma200": above_200,
                "btc_rsi14": rsi,
                "btc_trend": _trend_label(
                    above_50=above_50, above_200=above_200, rsi=rsi
                ),
                "updated_at": now,
            }
        )

    client = get_supabase()
    chunk = 500
    for i in range(0, len(rows), chunk):
        client.table("crypto_market_regime_daily").upsert(
            rows[i : i + chunk], on_conflict="date"
        ).execute()
    return len(rows)
