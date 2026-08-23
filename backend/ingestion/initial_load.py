"""Initial historical daily load — one EODHD request per instrument."""

from __future__ import annotations

import logging
import sys

from backend.data.eodhd import EodhdProvider, EodhdRequestLimitExceeded
from backend.ingestion.helpers import (
    finish_pipeline_run,
    list_active_instruments,
    start_pipeline_run,
    upsert_daily_prices,
)
from backend.ingestion.seed_instruments import seed_instruments

logger = logging.getLogger(__name__)


def run_initial_load(*, seed: bool = True) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if seed:
        seed_instruments()

    provider = EodhdProvider()
    run_id = start_pipeline_run("ingestion")
    summary: dict[str, int] = {}
    total_rows = 0

    try:
        instruments = list_active_instruments(asset_type="STOCK")
        if not instruments:
            raise RuntimeError("No active STOCK instruments in database. Run seed first.")

        from_date = provider.default_history_from_date()
        for inst in instruments:
            ticker = inst["ticker"]
            symbol = inst["symbol"]
            logger.info("Loading %s (%s) from %s", ticker, symbol, from_date)
            candles = provider.get_daily_data(symbol, from_date=from_date)
            n = upsert_daily_prices(inst["id"], candles)
            summary[ticker] = n
            total_rows += n
            print(f"{ticker:8} {n} rows")

        detail = {
            "mode": "initial_load",
            "asset_type": "STOCK",
            "provider": "EODHD",
            "per_ticker": summary,
            "total_rows": total_rows,
        }
        finish_pipeline_run(
            run_id,
            status="success",
            detail=detail,
            api_requests_used=provider.requests_used,
        )

        print()
        print("Initial load completed")
        print()
        print(f"Total: {total_rows} daily candles")
        print(f"API requests: {provider.requests_used}")
        return detail

    except EodhdRequestLimitExceeded as exc:
        finish_pipeline_run(
            run_id,
            status="failed",
            detail={"error": str(exc), "per_ticker": summary},
            api_requests_used=provider.requests_used,
        )
        raise
    except Exception as exc:
        finish_pipeline_run(
            run_id,
            status="failed",
            detail={"error": str(exc), "per_ticker": summary},
            api_requests_used=provider.requests_used,
        )
        raise


def main() -> None:
    try:
        run_initial_load(seed=True)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
