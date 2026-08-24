"""FreeCryptoAPI market data provider.

HTTP surface (official docs / SDK):
  Base URL: https://api.freecryptoapi.com/v1
  Auth: Authorization: Bearer <FREECRYPTOAPI_API_KEY>

Endpoints used:
  GET /getOHLC      — historical daily OHLCV
  GET /getData      — latest quote
  GET /getTop       — market-cap ranking

A vendored SDK copy lives at ``freecryptoapi_sdk.py`` for reference only.
This provider uses ``httpx`` (same stack as EODHD) so indicators never
depend on FreeCryptoAPI client code.

Daily candle convention
-----------------------
Candles are stored by calendar ``date`` (YYYY-MM-DD) exactly as returned by
``/getOHLC``. We treat each candle date as a UTC calendar day boundary and
never convert timezones. Crypto trades 24/7 — missing calendar days are
data gaps (logged), not "market closed".

References:
  https://freecryptoapi.com/sdk
  https://freecryptoapi.com/documentation/
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from backend.config import get_settings
from backend.data.provider import MarketDataProvider

logger = logging.getLogger(__name__)

BASE_URL = "https://api.freecryptoapi.com/v1"


class FreeCryptoAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


class FreeCryptoRequestLimitExceeded(RuntimeError):
    """Raised when the configured per-run FreeCryptoAPI budget is exhausted."""


class FreeCryptoAPIProvider(MarketDataProvider):
    """MarketDataProvider backed by FreeCryptoAPI daily OHLC."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        max_requests: int | None = None,
        timeout: float = 30.0,
    ) -> None:
        settings = get_settings()
        self.api_key = (
            api_key if api_key is not None else settings.freecryptoapi_api_key
        )
        self.max_requests = (
            max_requests
            if max_requests is not None
            else settings.max_freecryptoapi_requests_per_run
        )
        self.timeout = timeout
        self.requests_used = 0
        self._ohlc_plan_blocked = False

        if not self.api_key:
            raise RuntimeError(
                "FREECRYPTOAPI_API_KEY is empty. Set it in .env before calling FreeCryptoAPI."
            )

    def _budget_check(self) -> None:
        if self.requests_used >= self.max_requests:
            raise FreeCryptoRequestLimitExceeded(
                f"FreeCryptoAPI request budget exhausted "
                f"({self.requests_used}/{self.max_requests})"
            )

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        self._budget_check()
        query = {k: v for k, v in (params or {}).items() if v is not None}
        url = f"{BASE_URL}{endpoint}"
        logger.info("FreeCryptoAPI GET %s params=%s", endpoint, query)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                url,
                params=query,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                },
            )
            self.requests_used += 1
            if not response.is_success:
                try:
                    body = response.json()
                    message = (
                        body.get("message")
                        or body.get("error")
                        or response.text
                    )
                except Exception:
                    message = response.text
                raise FreeCryptoAPIError(response.status_code, str(message))
            body = response.json()
            # FreeCryptoAPI often returns HTTP 200 with status=false on plan limits
            if isinstance(body, dict) and body.get("status") in (False, "false", "error"):
                message = str(body.get("error") or body.get("message") or "API error")
                raise FreeCryptoAPIError(403, message)
            return body

    def get_daily_data(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Prefer FreeCryptoAPI /getOHLC; fall back to Binance public daily klines.

        Free tiers frequently block historical endpoints while still allowing
        /getData. Binance fallback keeps Vortex/triggers usable without mixing
        stock EODHD traffic.
        """
        today = to_date or date.today()
        candles: list[dict[str, Any]] = []
        plan_blocked = self._ohlc_plan_blocked
        if not self._ohlc_plan_blocked:
            try:
                if from_date is not None:
                    raw = self._get(
                        "/getOHLC",
                        {
                            "symbol": symbol,
                            "start_date": from_date.isoformat(),
                            "end_date": today.isoformat(),
                        },
                    )
                else:
                    days = get_settings().crypto_history_days
                    raw = self._get("/getOHLC", {"symbol": symbol, "days": days})
                candles = parse_ohlc_payload(raw)
            except FreeCryptoAPIError as exc:
                msg = (exc.message or "").lower()
                if "upgrade" in msg or "plan" in msg or "historical" in msg or "no access" in msg:
                    self._ohlc_plan_blocked = True
                    plan_blocked = True
                logger.warning(
                    "FreeCryptoAPI OHLC unavailable for %s (%s) — trying Binance daily fallback",
                    symbol,
                    exc.message,
                )

        if not candles:
            from backend.data.binance_ohlc import fetch_binance_daily

            start = from_date or self.default_history_from_date()
            candles = fetch_binance_daily(
                symbol, from_date=start, to_date=today, timeout=self.timeout
            )
            if candles:
                logger.info(
                    "Binance fallback filled %s candles for %s%s",
                    len(candles),
                    symbol,
                    " (FreeCryptoAPI plan blocked history)" if plan_blocked else "",
                )

        if from_date is not None:
            candles = [
                c
                for c in candles
                if date.fromisoformat(c["date"]) >= from_date
            ]
        if to_date is not None:
            candles = [
                c
                for c in candles
                if date.fromisoformat(c["date"]) <= to_date
            ]
        candles.sort(key=lambda c: c["date"])
        return candles

    def get_latest_data(self, symbol: str) -> dict[str, Any] | None:
        raw = self._get("/getData", {"symbol": symbol})
        quotes = parse_quote_payload(raw)
        return quotes[0] if quotes else None

    def get_latest_many(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """Batch live quotes via /getData (BTC+ETH+...)."""
        if not symbols:
            return {}
        out: dict[str, dict[str, Any]] = {}
        # FreeCryptoAPI accepts + joined symbols
        chunk_size = 10
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i : i + chunk_size]
            joined = "+".join(chunk)
            try:
                raw = self._get("/getData", {"symbol": joined})
            except FreeCryptoAPIError as exc:
                logger.warning("getData batch failed: %s", exc.message)
                continue
            for q in parse_quote_payload(raw):
                sym = q.get("symbol")
                if sym:
                    out[str(sym).upper()] = q
        return out

    def get_hourly_data(
        self,
        symbol: str,
        *,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "Hourly FreeCryptoAPI candles are deferred (future crypto 1H/4H)."
        )

    def get_top(self, n: int) -> list[dict[str, Any]]:
        try:
            raw = self._get("/getTop", {"top": n})
            ranked = parse_top_payload(raw)
            if ranked:
                return ranked
        except FreeCryptoAPIError as exc:
            logger.warning("getTop unavailable (%s) — caller should use fallback list", exc.message)
        return []

    def default_history_from_date(self) -> date:
        return date.today() - timedelta(days=get_settings().crypto_history_days)


def _as_list(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("data", "result", "ohlc", "candles", "history", "symbols", "coins"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _as_list(value)
            if nested:
                return nested
    if any(k in payload for k in ("open", "o", "close", "c", "price")):
        return [payload]
    return []


def _pick(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    lower = {str(k).lower(): v for k, v in item.items()}
    for key in keys:
        if key.lower() in lower and lower[key.lower()] is not None:
            return lower[key.lower()]
    return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_date_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        ts = int(text)
        if ts > 10_000_000_000:
            ts //= 1000
        return datetime.utcfromtimestamp(ts).date().isoformat()
    if "T" in text:
        text = text.split("T", 1)[0]
    if " " in text:
        text = text.split(" ", 1)[0]
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def parse_ohlc_candle(item: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    d = _to_date_str(_pick(item, "date", "time", "timestamp", "day", "t"))
    o = _to_float(_pick(item, "open", "o", "Open"))
    h = _to_float(_pick(item, "high", "h", "High"))
    low = _to_float(_pick(item, "low", "l", "Low"))
    c = _to_float(_pick(item, "close", "c", "Close", "price"))
    if d is None or o is None or h is None or low is None or c is None:
        return None
    vol = _to_float(_pick(item, "volume", "vol", "v", "Volume"))
    return {
        "date": d,
        "open": o,
        "high": h,
        "low": low,
        "close": c,
        "adjusted_close": None,
        "volume": int(vol) if vol is not None else 0,
    }


def parse_ohlc_payload(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _as_list(payload):
        if not isinstance(item, dict):
            continue
        candle = parse_ohlc_candle(item)
        if candle is None:
            continue
        if candle["date"] in seen:
            continue
        seen.add(candle["date"])
        rows.append(candle)
    rows.sort(key=lambda r: r["date"])
    return rows


def parse_quote_payload(payload: Any) -> list[dict[str, Any]]:
    quotes: list[dict[str, Any]] = []
    for item in _as_list(payload):
        if not isinstance(item, dict):
            continue
        symbol = _pick(item, "symbol", "ticker", "coin", "code", "name")
        price = _to_float(
            _pick(
                item,
                "last",
                "price",
                "price_usd",
                "close",
                "rate",
                "usd",
            )
        )
        change_24h = _to_float(
            _pick(
                item,
                "daily_change_percentage",
                "change_24h",
                "change24h",
                "percent_change_24h",
                "change_pct_24h",
                "change",
                "price_change_percentage_24h",
            )
        )
        # FreeCryptoAPI getData returns ratio (0.007 = +0.7%), not percent points
        # Only scale when clearly already percent-like (> ~1.5 absolute)
        if change_24h is not None and abs(change_24h) > 1.5:
            change_24h = change_24h / 100.0
        market_cap = _to_float(
            _pick(item, "market_cap", "marketcap", "mcap", "market_cap_usd")
        )
        name = _pick(item, "name", "full_name", "coin_name")
        quotes.append(
            {
                "symbol": str(symbol).upper() if symbol else None,
                "name": name,
                "price": price,
                "change_24h": change_24h,
                "market_cap": market_cap,
                "raw": item,
            }
        )
    return quotes


def parse_top_payload(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(_as_list(payload), start=1):
        if not isinstance(item, dict):
            continue
        symbol = _pick(item, "symbol", "ticker", "coin", "code")
        if not symbol:
            continue
        name = _pick(item, "name", "full_name", "coin_name") or str(symbol)
        rank = _pick(item, "rank", "market_cap_rank", "position")
        try:
            rank_i = int(rank) if rank is not None else idx
        except (TypeError, ValueError):
            rank_i = idx
        market_cap = _to_float(
            _pick(item, "market_cap", "marketcap", "mcap", "market_cap_usd")
        )
        price = _to_float(_pick(item, "price", "price_usd", "last", "close"))
        change_24h = _to_float(
            _pick(
                item,
                "change_24h",
                "change24h",
                "percent_change_24h",
                "price_change_percentage_24h",
            )
        )
        if change_24h is not None and abs(change_24h) > 1.5:
            change_24h = change_24h / 100.0
        rows.append(
            {
                "rank": rank_i,
                "symbol": str(symbol).upper(),
                "api_symbol": str(symbol).upper(),
                "name": str(name),
                "market_cap": market_cap,
                "price": price,
                "change_24h": change_24h,
            }
        )
    rows.sort(key=lambda r: r["rank"])
    return rows


def validate_candle(candle: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    try:
        o = float(candle["open"])
        h = float(candle["high"])
        low = float(candle["low"])
        c = float(candle["close"])
    except (KeyError, TypeError, ValueError):
        return ["invalid_ohlc_types"]
    if h < low:
        issues.append("high_lt_low")
    if c > h or c < low:
        issues.append("close_outside_range")
    if o > h or o < low:
        issues.append("open_outside_range")
    vol = candle.get("volume")
    if vol is not None:
        try:
            if float(vol) < 0:
                issues.append("negative_volume")
        except (TypeError, ValueError):
            issues.append("invalid_volume")
    return issues
