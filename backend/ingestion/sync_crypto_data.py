"""Incremental CRYPTO daily sync — FreeCryptoAPI only."""

from __future__ import annotations

import logging
import sys
from datetime import date

from backend.data.freecryptoapi import (
    FreeCryptoAPIProvider,
    FreeCryptoRequestLimitExceeded,
    validate_candle,
)
from backend.indicators.calculate_daily import calculate_for_all
from backend.ingestion.helpers import (
    finish_pipeline_run,
    last_daily_date,
    list_active_instruments,
    next_day,
    start_pipeline_run,
    upsert_daily_prices,
)
from backend.ingestion.seed_crypto import sync_crypto_universe

logger = logging.getLogger(__name__)


def run_sync_crypto(*, recalculate: bool = True) -> dict:
    """1) refresh TOP-N  2) incremental OHLC  3) optional calculate CRYPTO only."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    provider = FreeCryptoAPIProvider()
    run_id = start_pipeline_run("ingestion_crypto")
    summary: dict[str, int] = {}
    skipped: list[str] = []
    quality: dict[str, list[str]] = {}
    total_rows = 0

    try:
        universe = sync_crypto_universe(provider=provider, use_api_ranking=True)
        instruments = list_active_instruments(asset_type="CRYPTO")
        today = date.today()

        for inst in instruments:
            ticker = inst["ticker"]
            api_symbol = inst.get("api_symbol") or inst["ticker"]
            last = last_daily_date(inst["id"])

            # Crypto is 24/7 — still one daily candle per UTC calendar date.
            if last is not None and last >= today:
                skipped.append(ticker)
                summary[ticker] = 0
                logger.info("%s already up to date (last=%s)", ticker, last)
                continue

            from_date = (
                next_day(last)
                if last is not None
                else provider.default_history_from_date()
            )
            if from_date > today:
                skipped.append(ticker)
                summary[ticker] = 0
                continue

            logger.info("Sync crypto %s from %s", ticker, from_date)
            candles = provider.get_daily_data(
                api_symbol, from_date=from_date, to_date=today
            )
            if last is not None:
                candles = [c for c in candles if date.fromisoformat(c["date"]) > last]

            clean: list[dict] = []
            issues: list[str] = []
            for c in candles:
                bad = validate_candle(c)
                if bad:
                    issues.extend(bad)
                    continue
                clean.append(c)
            if issues:
                quality[ticker] = sorted(set(issues))

            n = upsert_daily_prices(inst["id"], clean)
            summary[ticker] = n
            total_rows += n
            print(f"{ticker:8} +{n} rows (from {from_date})")

        detail = {
            "mode": "sync_crypto",
            "asset_type": "CRYPTO",
            "provider": "FreeCryptoAPI",
            "universe": universe,
            "per_ticker": summary,
            "skipped": skipped,
            "quality_issues": quality,
            "total_rows": total_rows,
            "api_requests_used": provider.requests_used,
            "candle_timezone": "UTC calendar date as returned by FreeCryptoAPI /getOHLC",
        }
        finish_pipeline_run(
            run_id,
            status="success",
            detail=detail,
            api_requests_used=provider.requests_used,
        )

        calc_detail = None
        if recalculate:
            calc_detail = calculate_for_all(asset_type="CRYPTO")
            detail["calculation"] = calc_detail

        print()
        print(
            f"Crypto sync completed — {total_rows} new rows, "
            f"API requests: {provider.requests_used}"
        )
        return detail

    except FreeCryptoRequestLimitExceeded as exc:
        finish_pipeline_run(
            run_id,
            status="failed",
            detail={"error": str(exc), "per_ticker": summary, "asset_type": "CRYPTO"},
            api_requests_used=provider.requests_used,
        )
        raise
    except Exception as exc:
        finish_pipeline_run(
            run_id,
            status="failed",
            detail={"error": str(exc), "per_ticker": summary, "asset_type": "CRYPTO"},
            api_requests_used=provider.requests_used,
        )
        raise


def main() -> None:
    try:
        run_sync_crypto(recalculate=True)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
