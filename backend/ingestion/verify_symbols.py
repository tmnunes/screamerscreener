"""Verify Portuguese/US symbols against EODHD (uses API budget carefully)."""

from __future__ import annotations

import logging

from backend.data.eodhd import EodhdProvider
from backend.data.instruments import get_active_instruments

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    provider = EodhdProvider(max_requests=5)

    by_exchange: dict[str, list[str]] = {}
    for inst in get_active_instruments():
        by_exchange.setdefault(inst.exchange, []).append(inst.ticker)

    print("Verifying symbols via EODHD exchange-symbol-list (1 request per exchange)...\n")
    ok = True
    for exchange, tickers in by_exchange.items():
        rows = provider.exchange_symbols(exchange, symbols=tickers)
        found = {r.get("Code") for r in rows}
        print(f"[{exchange}] requested={tickers}")
        for t in tickers:
            status = "OK" if t in found else "MISSING"
            if status == "MISSING":
                ok = False
            print(f"  {t:6} {status}")
        print()

    print(f"API requests used: {provider.requests_used}")
    if not ok:
        raise SystemExit(1)
    print("All configured symbols found.")


if __name__ == "__main__":
    main()
