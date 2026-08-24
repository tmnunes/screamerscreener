"""Public Binance daily klines — OHLC fallback when FreeCryptoAPI plan blocks history.

No API key required. Used only for CRYPTO historical candles so Vortex/triggers
can run on free FreeCryptoAPI tiers that allow /getData but not /getOHLC.

Endpoint: GET https://api.binance.com/api/v3/klines
Interval: 1d (UTC day boundary — matches Binance candle open time in UTC).

Pair mapping: SYMBOL -> SYMBOLUSDT (stablecoins / missing pairs return []).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"

# Symbols that are not useful as USDT spot pairs for this screener
_SKIP = {"USDT", "USDC", "DAI", "FDUSD", "TUSD", "BUSD"}


def binance_pair(api_symbol: str) -> str | None:
    sym = api_symbol.upper().strip()
    if not sym or sym in _SKIP:
        return None
    # Common renames
    aliases = {"MATIC": "MATIC", "POL": "POL"}
    sym = aliases.get(sym, sym)
    return f"{sym}USDT"


def fetch_binance_daily(
    api_symbol: str,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 1000,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """Return ScreamerScreener candle dicts for SYMBOLUSDT daily klines."""
    pair = binance_pair(api_symbol)
    if not pair:
        logger.info("Binance skip %s (no USDT pair / stablecoin)", api_symbol)
        return []

    params: dict[str, Any] = {"symbol": pair, "interval": "1d", "limit": min(limit, 1000)}
    if from_date is not None:
        start = datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
        params["startTime"] = int(start.timestamp() * 1000)
    if to_date is not None:
        end = datetime(to_date.year, to_date.month, to_date.day, 23, 59, 59, tzinfo=timezone.utc)
        params["endTime"] = int(end.timestamp() * 1000)

    logger.info("Binance klines %s params=%s", pair, {k: v for k, v in params.items() if k != "symbol"})
    with httpx.Client(timeout=timeout) as client:
        response = client.get(BINANCE_KLINES, params=params)
        if response.status_code == 400:
            logger.warning("Binance pair unavailable for %s: %s", pair, response.text[:200])
            return []
        response.raise_for_status()
        raw = response.json()

    if not isinstance(raw, list):
        return []

    candles: list[dict[str, Any]] = []
    for row in raw:
        # [open_time, open, high, low, close, volume, close_time, ...]
        if not isinstance(row, list) or len(row) < 6:
            continue
        open_ms = int(row[0])
        d = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc).date()
        if from_date and d < from_date:
            continue
        if to_date and d > to_date:
            continue
        candles.append(
            {
                "date": d.isoformat(),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "adjusted_close": None,
                "volume": int(float(row[5])),
            }
        )
    candles.sort(key=lambda c: c["date"])
    return candles
