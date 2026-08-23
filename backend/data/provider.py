"""Data provider interface.

Implementations must never be called from the frontend.
EODHD credentials stay server-side only.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any

from backend.data import Timeframe


class MarketDataProvider(ABC):
    """Abstract market data provider (EODHD in production)."""

    @abstractmethod
    def get_daily_data(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch daily OHLCV candles for a symbol."""

    @abstractmethod
    def get_hourly_data(
        self,
        symbol: str,
        *,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch hourly OHLCV candles (not used in Phase 1)."""

    def supports(self, timeframe: Timeframe) -> bool:
        return timeframe in {Timeframe.DAILY, Timeframe.HOURLY}
