"""Quantitative research defaults for crypto perpetual futures."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data" / "research"
RAW_DIR = DATA_ROOT / "raw"
NORMALIZED_DIR = DATA_ROOT / "normalized"
CACHE_DIR = DATA_ROOT / "cache"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

# Binance USD-M perpetual futures public data
VISION_BASE = "https://data.binance.vision/data/futures/um/monthly"
FAPI_KLINES_URLS = (
    "https://fapi.binance.com/fapi/v1/klines",
    "https://data-api.binance.vision/api/v1/klines",  # may not support futures
)
FAPI_FUNDING_URLS = (
    "https://fapi.binance.com/fapi/v1/fundingRate",
)

PRIMARY_SYMBOLS = ("BTCUSDT", "ETHUSDT")
EXTRA_LIQUID_SYMBOLS = ("SOLUSDT", "BNBUSDT", "XRPUSDT")

# Preferred research window (UTC). Latest complete month resolved at runtime.
DEFAULT_START_YEAR = 2024
DEFAULT_START_MONTH = 10

NATIVE_INTERVAL = "5m"
AGGREGATE_INTERVALS = ("15m", "30m", "1h")

# Execution cost assumptions (documented; configurable in backtests)
DEFAULT_TAKER_FEE = 0.0004  # 4 bps per side (Binance UM VIP0-ish conservative)
DEFAULT_MAKER_FEE = 0.0002
DEFAULT_SLIPPAGE_BPS = 1.5  # 1.5 bps per side
DEFAULT_LEVERAGE = 1.0
DEFAULT_INITIAL_EQUITY = 100_000.0


@dataclass(slots=True)
class CostModel:
    taker_fee: float = DEFAULT_TAKER_FEE
    maker_fee: float = DEFAULT_MAKER_FEE
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS
    use_taker: bool = True

    @property
    def fee_rate(self) -> float:
        return self.taker_fee if self.use_taker else self.maker_fee

    @property
    def slippage_rate(self) -> float:
        return self.slippage_bps / 10_000.0


@dataclass(slots=True)
class ResearchUniverse:
    symbols: tuple[str, ...] = field(
        default_factory=lambda: PRIMARY_SYMBOLS + EXTRA_LIQUID_SYMBOLS
    )
    start_year: int = DEFAULT_START_YEAR
    start_month: int = DEFAULT_START_MONTH
