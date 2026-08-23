"""Data provider interface.

Implementations must never be called from the frontend.
Provider credentials (EODHD / FreeCryptoAPI) stay server-side only.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any

from backend.data import Timeframe


class MarketDataProvider(ABC):
    """Abstract market data provider.

    Concrete implementations:
      - EodhdProvider (STOCK)
      - FreeCryptoAPIProvider (CRYPTO)
    """

    @abstractmethod
    def get_daily_data(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch daily OHLCV candles for a symbol."""

    def get_latest_data(self, symbol: str) -> dict[str, Any] | None:
        """Optional latest quote. Default: unsupported."""
        return None

    @abstractmethod
    def get_hourly_data(
        self,
        symbol: str,
        *,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch hourly OHLCV candles (reserved for future use)."""

    def supports(self, timeframe: Timeframe) -> bool:
        return timeframe in {Timeframe.DAILY, Timeframe.HOURLY}
