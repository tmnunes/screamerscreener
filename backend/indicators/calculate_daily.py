"""Calculate Vortex Bands, detect triggers, and update performance."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from backend.backtest.performance import calculate_performance_from_closes
from backend.db import get_supabase
from backend.indicators.vortex_bands import (
    DEFAULT_LENGTH,
    DEFAULT_MULT,
    DEFAULT_SOURCE,
    calculate_vortex_bands,
)
from backend.ingestion.helpers import finish_pipeline_run, list_active_instruments, start_pipeline_run
from backend.signals.vortex_triggers import detect_triggers

logger = logging.getLogger(__name__)


def _fetch_prices(instrument_id: str) -> list[dict[str, Any]]:
    client = get_supabase()
    result = (
        client.table("market_prices_daily")
        .select("date,open,high,low,close,adjusted_close,volume")
        .eq("instrument_id", instrument_id)
        .order("date")
        .execute()
    )
    return list(result.data or [])


def _upsert_indicators(
    instrument_id: str,
    prices: list[dict[str, Any]],
    *,
    length: int,
    mult: float,
    source: str,
) -> int:
    highs = [float(p["high"]) for p in prices]
    lows = [float(p["low"]) for p in prices]
    closes = [float(p["close"]) for p in prices]
    bands = calculate_vortex_bands(
        highs, lows, closes, length=length, mult=mult, source=source
    )

    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for price, band in zip(prices, bands):
        rows.append(
            {
                "instrument_id": instrument_id,
                "date": price["date"],
                "basis": band.basis,
                "upper": band.upper,
                "lower": band.lower,
                "length": length,
                "mult": mult,
                "source": source,
                "updated_at": now,
            }
        )

    client = get_supabase()
    chunk_size = 500
    for i in range(0, len(rows), chunk_size):
        client.table("indicator_values_daily").upsert(
            rows[i : i + chunk_size],
            on_conflict="instrument_id,date,length,mult,source",
        ).execute()
    return len(rows)


def _upsert_triggers(
    instrument_id: str,
    prices: list[dict[str, Any]],
    *,
    length: int,
    mult: float,
    source: str,
) -> list[dict[str, Any]]:
    highs = [float(p["high"]) for p in prices]
    lows = [float(p["low"]) for p in prices]
    closes = [float(p["close"]) for p in prices]
    bands = calculate_vortex_bands(
        highs, lows, closes, length=length, mult=mult, source=source
    )
    basis = [b.basis for b in bands]
    upper = [b.upper for b in bands]
    lower = [b.lower for b in bands]

    events = detect_triggers(closes, basis, upper, lower)
    rows = []
    for event in events:
        rows.append(
            {
                "instrument_id": instrument_id,
                "date": prices[event.index]["date"],
                "trigger_type": event.trigger_type.value,
                "trigger_price": event.trigger_price,
                "basis": event.basis,
                "upper": event.upper,
                "lower": event.lower,
                "previous_basis": event.previous_basis,
                "previous_upper": event.previous_upper,
                "previous_lower": event.previous_lower,
                "previous_close": event.previous_close,
                "length": length,
                "mult": mult,
                "source": source,
            }
        )

    client = get_supabase()
    if rows:
        client.table("triggers_daily").upsert(
            rows,
            on_conflict="instrument_id,date,trigger_type,length,mult,source",
        ).execute()
    return rows


def _update_performance_for_instrument(
    instrument_id: str,
    prices: list[dict[str, Any]],
    *,
    length: int,
    mult: float,
    source: str,
) -> int:
    client = get_supabase()
    triggers = (
        client.table("triggers_daily")
        .select("id,date,trigger_type,trigger_price")
        .eq("instrument_id", instrument_id)
        .eq("length", length)
        .eq("mult", mult)
        .eq("source", source)
        .execute()
    ).data or []

    date_to_idx = {p["date"]: i for i, p in enumerate(prices)}
    closes = [float(p["close"]) for p in prices]
    updated = 0

    for trig in triggers:
        idx = date_to_idx.get(trig["date"])
        if idx is None:
            continue
        closes_after = closes[idx + 1 :]
        perf = calculate_performance_from_closes(
            trigger_type=trig["trigger_type"],
            trigger_price=float(trig["trigger_price"]),
            closes_after=closes_after,
        )
        row = {
            "trigger_id": trig["id"],
            "return_1d": perf.return_1d,
            "return_3d": perf.return_3d,
            "return_5d": perf.return_5d,
            "return_10d": perf.return_10d,
            "return_20d": perf.return_20d,
            "max_favorable_return": perf.max_favorable_return,
            "max_adverse_return": perf.max_adverse_return,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        }
        client.table("trigger_performance").upsert(
            row, on_conflict="trigger_id"
        ).execute()
        updated += 1
    return updated


def calculate_for_all(
    *,
    length: int = DEFAULT_LENGTH,
    mult: float = DEFAULT_MULT,
    source: str = DEFAULT_SOURCE,
) -> dict[str, Any]:
    run_id = start_pipeline_run("calculation")
    per_ticker: dict[str, Any] = {}

    try:
        instruments = list_active_instruments()
        for inst in instruments:
            ticker = inst["ticker"]
            prices = _fetch_prices(inst["id"])
            if len(prices) < 2:
                per_ticker[ticker] = {"prices": len(prices), "indicators": 0, "triggers": 0}
                continue

            n_ind = _upsert_indicators(
                inst["id"], prices, length=length, mult=mult, source=source
            )
            triggers = _upsert_triggers(
                inst["id"], prices, length=length, mult=mult, source=source
            )
            n_perf = _update_performance_for_instrument(
                inst["id"], prices, length=length, mult=mult, source=source
            )
            per_ticker[ticker] = {
                "prices": len(prices),
                "indicators": n_ind,
                "triggers": len(triggers),
                "performance": n_perf,
            }
            print(
                f"{ticker:8} prices={len(prices)} indicators={n_ind} "
                f"triggers={len(triggers)} perf={n_perf}"
            )

        detail = {
            "length": length,
            "mult": mult,
            "source": source,
            "per_ticker": per_ticker,
        }
        finish_pipeline_run(
            run_id, status="success", detail=detail, api_requests_used=0
        )
        return detail
    except Exception as exc:
        finish_pipeline_run(
            run_id,
            status="failed",
            detail={"error": str(exc), "per_ticker": per_ticker},
            api_requests_used=0,
        )
        raise


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Calculate Vortex Bands + triggers")
    parser.add_argument("--length", type=int, default=DEFAULT_LENGTH)
    parser.add_argument("--mult", type=float, default=DEFAULT_MULT)
    parser.add_argument("--source", type=str, default=DEFAULT_SOURCE)
    args = parser.parse_args()

    try:
        calculate_for_all(length=args.length, mult=args.mult, source=args.source)
        print("Calculation completed")
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
