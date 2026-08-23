"""Phase 6 — validate stored market data integrity."""

from __future__ import annotations

import logging
from datetime import date

from backend.db import get_supabase
from backend.ingestion.helpers import list_active_instruments

logger = logging.getLogger(__name__)


def validate_database_data() -> dict:
    client = get_supabase()
    instruments = list_active_instruments()
    report = {
        "instruments": len(instruments),
        "per_ticker": {},
        "issues": [],
    }

    for inst in instruments:
        ticker = inst["ticker"]
        rows = (
            client.table("market_prices_daily")
            .select("date,open,high,low,close")
            .eq("instrument_id", inst["id"])
            .order("date")
            .execute()
        ).data or []

        dates = [r["date"] for r in rows]
        dupes = len(dates) - len(set(dates))
        ohlc_bad = 0
        for r in rows:
            o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
            if h < max(o, c) or l > min(o, c) or h < l:
                ohlc_bad += 1

        entry = {
            "rows": len(rows),
            "first": dates[0] if dates else None,
            "last": dates[-1] if dates else None,
            "duplicate_dates": dupes,
            "ohlc_anomalies": ohlc_bad,
        }
        report["per_ticker"][ticker] = entry
        if not rows:
            report["issues"].append(f"{ticker}: no daily rows")
        if dupes:
            report["issues"].append(f"{ticker}: {dupes} duplicate dates")
        if ohlc_bad:
            report["issues"].append(f"{ticker}: {ohlc_bad} OHLC anomalies")

        print(
            f"{ticker:8} rows={len(rows):4} "
            f"{entry['first']} → {entry['last']} "
            f"dupes={dupes} ohlc_bad={ohlc_bad}"
        )

    print()
    if report["issues"]:
        print("Issues found:")
        for issue in report["issues"]:
            print(f"  - {issue}")
    else:
        print("Validation OK — no issues found")
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    validate_database_data()


if __name__ == "__main__":
    main()
