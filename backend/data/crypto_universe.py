"""Configurable crypto universe (TOP-N).

Primary source: FreeCryptoAPI ``/getTop``.
Fallback: CRYPTO_FALLBACK_TOP list below (used when API ranking fails).

CRYPTO_TOP_N (env) controls how many coins stay active in the screener.
Coins that fall out of TOP-N are marked ``in_top_universe=false`` and
``active=false`` (historical prices retained).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from backend.config import get_settings


@dataclass(frozen=True, slots=True)
class CryptoInstrumentConfig:
    ticker: str
    api_symbol: str
    name: str
    rank: int
    currency: str = "USD"
    active: bool = True

    def as_row(self) -> dict:
        return {
            "ticker": self.ticker,
            "symbol": f"{self.api_symbol}.CRYPTO",
            "api_symbol": self.api_symbol,
            "exchange": "CRYPTO",
            "country": "GLOBAL",
            "name": self.name,
            "currency": self.currency,
            "active": self.active,
            "asset_type": "CRYPTO",
            "crypto_rank": self.rank,
            "in_top_universe": self.active,
        }


# Fallback TOP 25 when /getTop is unavailable. Editable / overridable via sync.
CRYPTO_FALLBACK_TOP: tuple[CryptoInstrumentConfig, ...] = (
    CryptoInstrumentConfig("BTC", "BTC", "Bitcoin", 1),
    CryptoInstrumentConfig("ETH", "ETH", "Ethereum", 2),
    CryptoInstrumentConfig("USDT", "USDT", "Tether", 3),
    CryptoInstrumentConfig("BNB", "BNB", "BNB", 4),
    CryptoInstrumentConfig("XRP", "XRP", "XRP", 5),
    CryptoInstrumentConfig("USDC", "USDC", "USD Coin", 6),
    CryptoInstrumentConfig("SOL", "SOL", "Solana", 7),
    CryptoInstrumentConfig("ADA", "ADA", "Cardano", 8),
    CryptoInstrumentConfig("DOGE", "DOGE", "Dogecoin", 9),
    CryptoInstrumentConfig("TRX", "TRX", "TRON", 10),
    CryptoInstrumentConfig("TON", "TON", "Toncoin", 11),
    CryptoInstrumentConfig("DOT", "DOT", "Polkadot", 12),
    CryptoInstrumentConfig("LINK", "LINK", "Chainlink", 13),
    CryptoInstrumentConfig("MATIC", "MATIC", "Polygon", 14),
    CryptoInstrumentConfig("SHIB", "SHIB", "Shiba Inu", 15),
    CryptoInstrumentConfig("AVAX", "AVAX", "Avalanche", 16),
    CryptoInstrumentConfig("DAI", "DAI", "Dai", 17),
    CryptoInstrumentConfig("LTC", "LTC", "Litecoin", 18),
    CryptoInstrumentConfig("BCH", "BCH", "Bitcoin Cash", 19),
    CryptoInstrumentConfig("UNI", "UNI", "Uniswap", 20),
    CryptoInstrumentConfig("ATOM", "ATOM", "Cosmos", 21),
    CryptoInstrumentConfig("XLM", "XLM", "Stellar", 22),
    CryptoInstrumentConfig("OKB", "OKB", "OKB", 23),
    CryptoInstrumentConfig("ETC", "ETC", "Ethereum Classic", 24),
    CryptoInstrumentConfig("XMR", "XMR", "Monero", 25),
)


def crypto_top_n() -> int:
    return max(1, int(get_settings().crypto_top_n))


def get_fallback_top(n: int | None = None) -> list[CryptoInstrumentConfig]:
    limit = n if n is not None else crypto_top_n()
    return list(CRYPTO_FALLBACK_TOP[:limit])


def ranked_rows_to_configs(ranked: list[dict]) -> list[CryptoInstrumentConfig]:
    configs: list[CryptoInstrumentConfig] = []
    for item in ranked:
        symbol = str(item["symbol"]).upper()
        configs.append(
            CryptoInstrumentConfig(
                ticker=symbol,
                api_symbol=str(item.get("api_symbol") or symbol).upper(),
                name=str(item.get("name") or symbol),
                rank=int(item.get("rank") or len(configs) + 1),
            )
        )
    return configs
