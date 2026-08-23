"""Export price + Vortex series to CSV for TradingView comparison."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from backend.db import get_supabase
from backend.indicators.vortex_bands import (
    DEFAULT_LENGTH,
    DEFAULT_MULT,
    DEFAULT_SOURCE,
    calculate_vortex_bands,
)
from backend.signals.vortex_triggers import TriggerType, detect_triggers


def export_ticker(
    ticker: str,
    output: Path,
    *,
    length: int,
    mult: float,
    source: str,
) -> Path:
    client = get_supabase()
    inst = (
        client.table("market_instruments")
        .select("id,ticker")
        .eq("ticker", ticker.upper())
        .limit(1)
        .execute()
    ).data
    if not inst:
        raise SystemExit(f"Unknown ticker: {ticker}")

    instrument_id = inst[0]["id"]
    prices = (
        client.table("market_prices_daily")
        .select("date,open,high,low,close")
        .eq("instrument_id", instrument_id)
        .order("date")
        .execute()
    ).data or []

    highs = [float(p["high"]) for p in prices]
    lows = [float(p["low"]) for p in prices]
    closes = [float(p["close"]) for p in prices]
    bands = calculate_vortex_bands(
        highs, lows, closes, length=length, mult=mult, source=source
    )
    events = detect_triggers(
        closes,
        [b.basis for b in bands],
        [b.upper for b in bands],
        [b.lower for b in bands],
    )
    trigger_map: dict[int, list[str]] = {}
    for e in events:
        trigger_map.setdefault(e.index, []).append(e.trigger_type.value)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["date", "open", "high", "low", "close", "basis", "upper", "lower", "trigger"]
        )
        for i, price in enumerate(prices):
            writer.writerow(
                [
                    price["date"],
                    price["open"],
                    price["high"],
                    price["low"],
                    price["close"],
                    bands[i].basis,
                    bands[i].upper,
                    bands[i].lower,
                    "|".join(trigger_map.get(i, [])),
                ]
            )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--length", type=int, default=DEFAULT_LENGTH)
    parser.add_argument("--mult", type=float, default=DEFAULT_MULT)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    args = parser.parse_args()

    out = Path(args.out) if args.out else Path("exports") / f"{args.ticker.upper()}_vortex.csv"
    path = export_ticker(
        args.ticker, out, length=args.length, mult=args.mult, source=args.source
    )
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
