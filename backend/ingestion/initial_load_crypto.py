"""Initial historical daily load for CRYPTO — FreeCryptoAPI only."""

from __future__ import annotations

import logging
import sys
from datetime import date

from backend.data.freecryptoapi import (
    FreeCryptoAPIProvider,
    FreeCryptoRequestLimitExceeded,
    validate_candle,
)
from backend.ingestion.helpers import (
    finish_pipeline_run,
    last_daily_date,
    list_active_instruments,
    start_pipeline_run,
    upsert_daily_prices,
)
from backend.ingestion.seed_crypto import sync_crypto_universe

logger = logging.getLogger(__name__)


def run_initial_load_crypto(*, seed: bool = True) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    provider = FreeCryptoAPIProvider()
    run_id = start_pipeline_run("ingestion_crypto")
    summary: dict[str, int] = {}
    quality: dict[str, list[str]] = {}
    total_rows = 0
    universe: dict = {}

    try:
        if seed:
            universe = sync_crypto_universe(provider=provider, use_api_ranking=True)

        instruments = list_active_instruments(asset_type="CRYPTO")
        if not instruments:
            raise RuntimeError("No active CRYPTO instruments. Seed TOP-N first.")

        from_date = provider.default_history_from_date()
        for inst in instruments:
            ticker = inst["ticker"]
            api_symbol = inst.get("api_symbol") or inst["ticker"]
            last = last_daily_date(inst["id"])
            # Idempotent: skip full reload if we already have history
            if last is not None:
                logger.info("%s already has data through %s — skipping full reload", ticker, last)
                summary[ticker] = 0
                continue

            logger.info("Loading crypto %s (%s) from %s", ticker, api_symbol, from_date)
            candles = provider.get_daily_data(api_symbol, from_date=from_date)
            issues: list[str] = []
            clean: list[dict] = []
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
            print(f"{ticker:8} {n} rows")

        detail = {
            "mode": "initial_load_crypto",
            "asset_type": "CRYPTO",
            "provider": "FreeCryptoAPI",
            "universe": universe,
            "per_ticker": summary,
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
        print()
        print(f"Crypto initial load completed — {total_rows} candles")
        print(f"API requests: {provider.requests_used}")
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
        run_initial_load_crypto(seed=True)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
