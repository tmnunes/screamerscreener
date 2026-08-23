"""Incremental daily market data sync."""

from __future__ import annotations

import logging
import sys
from datetime import date

from backend.data.eodhd import EodhdProvider, EodhdRequestLimitExceeded
from backend.ingestion.helpers import (
    finish_pipeline_run,
    last_daily_date,
    list_active_instruments,
    next_day,
    start_pipeline_run,
    upsert_daily_prices,
)

logger = logging.getLogger(__name__)


def run_sync() -> dict:
    """Incremental sync for STOCK instruments only (EODHD)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    provider = EodhdProvider()
    run_id = start_pipeline_run("ingestion")
    summary: dict[str, int] = {}
    skipped: list[str] = []
    total_rows = 0

    try:
        instruments = list_active_instruments(asset_type="STOCK")
        today = date.today()

        for inst in instruments:
            ticker = inst["ticker"]
            last = last_daily_date(inst["id"])
            if last is not None and last >= today:
                skipped.append(ticker)
                summary[ticker] = 0
                logger.info("%s already up to date (last=%s)", ticker, last)
                continue

            from_date = next_day(last) if last is not None else provider.default_history_from_date()
            if from_date > today:
                skipped.append(ticker)
                summary[ticker] = 0
                continue

            logger.info("Sync %s from %s", ticker, from_date)
            candles = provider.get_daily_data(inst["symbol"], from_date=from_date)
            # Filter strictly after last to keep idempotent even if API overlaps
            if last is not None:
                candles = [c for c in candles if date.fromisoformat(c["date"]) > last]

            n = upsert_daily_prices(inst["id"], candles)
            summary[ticker] = n
            total_rows += n
            print(f"{ticker:8} +{n} rows (from {from_date})")

        detail = {
            "mode": "sync",
            "asset_type": "STOCK",
            "provider": "EODHD",
            "per_ticker": summary,
            "skipped": skipped,
            "total_rows": total_rows,
            "api_requests_used": provider.requests_used,
        }
        finish_pipeline_run(
            run_id,
            status="success",
            detail=detail,
            api_requests_used=provider.requests_used,
        )
        print()
        print(f"Sync completed — {total_rows} new rows, API requests: {provider.requests_used}")
        return detail

    except EodhdRequestLimitExceeded as exc:
        finish_pipeline_run(
            run_id,
            status="failed",
            detail={"error": str(exc), "per_ticker": summary, "asset_type": "STOCK"},
            api_requests_used=provider.requests_used,
        )
        raise
    except Exception as exc:
        finish_pipeline_run(
            run_id,
            status="failed",
            detail={"error": str(exc), "per_ticker": summary, "asset_type": "STOCK"},
            api_requests_used=provider.requests_used,
        )
        raise


def main() -> None:
    try:
        run_sync()
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
