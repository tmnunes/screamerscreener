"""EODHD market data provider."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from backend.config import get_settings
from backend.data.provider import MarketDataProvider

logger = logging.getLogger(__name__)

BASE_URL = "https://eodhd.com/api"


class EodhdRequestLimitExceeded(RuntimeError):
    """Raised when the configured per-run API budget would be exceeded."""


class EodhdProvider(MarketDataProvider):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        max_requests: int | None = None,
        timeout: float = 60.0,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.eodhd_api_key
        self.max_requests = (
            max_requests
            if max_requests is not None
            else settings.max_eodhd_requests_per_run
        )
        self.timeout = timeout
        self.requests_used = 0

        if not self.api_key:
            raise RuntimeError(
                "EODHD_API_KEY is empty. Set it in .env before calling EODHD."
            )

    def _budget_check(self) -> None:
        if self.requests_used >= self.max_requests:
            raise EodhdRequestLimitExceeded(
                f"EODHD request budget exhausted ({self.requests_used}/{self.max_requests})"
            )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._budget_check()
        query = {"api_token": self.api_key, "fmt": "json"}
        if params:
            query.update(params)

        url = f"{BASE_URL}{path}"
        logger.info("EODHD GET %s params=%s", path, {k: v for k, v in query.items() if k != "api_token"})
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, params=query)
            self.requests_used += 1
            response.raise_for_status()
            return response.json()

    def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        data = self._get("/search/" + query, params={"limit": limit})
        if not isinstance(data, list):
            return []
        return data

    def exchange_symbols(
        self,
        exchange: str,
        *,
        symbols: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if symbols:
            params["symbols"] = ",".join(symbols)
        data = self._get(f"/exchange-symbol-list/{exchange}", params=params)
        if not isinstance(data, list):
            return []
        return data

    def get_daily_data(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"period": "d"}
        if from_date is not None:
            params["from"] = from_date.isoformat()
        if to_date is not None:
            params["to"] = to_date.isoformat()

        data = self._get(f"/eod/{symbol}", params=params)
        if not isinstance(data, list):
            logger.warning("Unexpected EODHD response for %s: %s", symbol, type(data))
            return []

        rows: list[dict[str, Any]] = []
        for item in data:
            rows.append(
                {
                    "date": item["date"],
                    "open": float(item["open"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "close": float(item["close"]),
                    "adjusted_close": float(item.get("adjusted_close", item["close"])),
                    "volume": int(item.get("volume") or 0),
                }
            )
        return rows

    def get_hourly_data(
        self,
        symbol: str,
        *,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "Hourly EODHD downloads are deferred (Phase 1–18 architecture only)."
        )

    def default_history_from_date(self) -> date:
        """Approx 1 year of daily history for the free-tier initial load."""
        return date.today() - timedelta(days=370)
