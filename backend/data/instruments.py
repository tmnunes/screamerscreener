"""Canonical instrument universe configuration.

Portuguese symbols use Euronext Lisbon (LS) exchange codes on EODHD.
Confirm with: python -m backend.ingestion.verify_symbols
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class InstrumentConfig:
    ticker: str
    symbol: str
    exchange: str
    country: str
    name: str
    currency: str
    active: bool = True

    def as_row(self) -> dict:
        return asdict(self)


# Initial universe (~15 names). Symbols are EODHD format: TICKER.EXCHANGE
INSTRUMENTS: tuple[InstrumentConfig, ...] = (
    # Portugal — Euronext Lisbon (LS)
    InstrumentConfig("GALP", "GALP.LS", "LS", "Portugal", "Galp Energia", "EUR"),
    InstrumentConfig("EDP", "EDP.LS", "LS", "Portugal", "EDP", "EUR"),
    InstrumentConfig("EDPR", "EDPR.LS", "LS", "Portugal", "EDP Renováveis", "EUR"),
    InstrumentConfig("JMT", "JMT.LS", "LS", "Portugal", "Jerónimo Martins", "EUR"),
    InstrumentConfig("BCP", "BCP.LS", "LS", "Portugal", "Banco Comercial Português", "EUR"),
    # USA
    InstrumentConfig("AAPL", "AAPL.US", "US", "USA", "Apple", "USD"),
    InstrumentConfig("MSFT", "MSFT.US", "US", "USA", "Microsoft", "USD"),
    InstrumentConfig("NVDA", "NVDA.US", "US", "USA", "NVIDIA", "USD"),
    InstrumentConfig("AMZN", "AMZN.US", "US", "USA", "Amazon", "USD"),
    InstrumentConfig("GOOGL", "GOOGL.US", "US", "USA", "Alphabet", "USD"),
    InstrumentConfig("META", "META.US", "US", "USA", "Meta Platforms", "USD"),
    InstrumentConfig("TSLA", "TSLA.US", "US", "USA", "Tesla", "USD"),
    InstrumentConfig("AVGO", "AVGO.US", "US", "USA", "Broadcom", "USD"),
    InstrumentConfig("AMD", "AMD.US", "US", "USA", "AMD", "USD"),
    InstrumentConfig("JPM", "JPM.US", "US", "USA", "JPMorgan Chase", "USD"),
    # Market regime context (inactive by default — enable later; costs EODHD quota)
    InstrumentConfig(
        "SPY", "SPY.US", "US", "USA", "SPDR S&P 500 ETF", "USD", active=False
    ),
    InstrumentConfig(
        "QQQ", "QQQ.US", "US", "USA", "Invesco QQQ Trust", "USD", active=False
    ),
)


def get_active_instruments() -> list[InstrumentConfig]:
    return [i for i in INSTRUMENTS if i.active]
