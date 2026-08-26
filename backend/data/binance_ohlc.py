"""Public Binance daily klines — OHLC fallback when FreeCryptoAPI plan blocks history.

No API key required. Used only for CRYPTO historical candles so Vortex/triggers
can run on free FreeCryptoAPI tiers that allow /getData but not /getOHLC.

Primary endpoint: https://data-api.binance.vision/api/v3/klines
(``api.binance.com`` returns HTTP 451 from many cloud regions.)

Interval: 1d (UTC day boundary — matches Binance candle open time in UTC).

Pair mapping: SYMBOL -> SYMBOLUSDT (stablecoins / missing pairs return []).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Prefer the public market-data host; api.binance.com is geo-blocked (451) on
# common US cloud egress (Render, GitHub-hosted runners calling Render, etc.).
BINANCE_KLINES_URLS = (
    "https://data-api.binance.vision/api/v3/klines",
    "https://api.binance.us/api/v3/klines",
    "https://api.binance.com/api/v3/klines",
)
BINANCE_KLINES = BINANCE_KLINES_URLS[0]

# Soft-fail statuses: pair missing, geo-restriction, or forbidden — never abort refresh.
_SOFT_FAIL_STATUSES = {400, 403, 451}

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

    logger.info(
        "Binance klines %s params=%s",
        pair,
        {k: v for k, v in params.items() if k != "symbol"},
    )

    raw: Any = None
    last_error: str | None = None
    with httpx.Client(timeout=timeout) as client:
        for url in BINANCE_KLINES_URLS:
            response = client.get(url, params=params)
            if response.status_code in _SOFT_FAIL_STATUSES:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(
                    "Binance soft-fail for %s via %s — %s",
                    pair,
                    url,
                    last_error,
                )
                continue
            if not response.is_success:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(
                    "Binance error for %s via %s — %s",
                    pair,
                    url,
                    last_error,
                )
                continue
            raw = response.json()
            break

    if raw is None:
        if last_error:
            logger.warning("Binance unavailable for %s after trying all hosts (%s)", pair, last_error)
        return []

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
