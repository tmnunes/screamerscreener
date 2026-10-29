#!/usr/bin/env python3
"""Download Binance UM futures 5m + funding into data/research/raw.

Run outside restricted sandboxes if data.binance.vision is blocked:

  cd /path/to/screamerscreener
  source .venv/bin/activate
  python scripts/download_research_data.py
  python -m backend.research.runner --run
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.research.config import PRIMARY_SYMBOLS  # noqa: E402
from backend.research.data.download import latest_complete_month  # noqa: E402
from backend.research.data.store import build_symbol_datasets  # noqa: E402


def main() -> int:
    start = date(2024, 10, 1)
    end = latest_complete_month()
    for symbol in PRIMARY_SYMBOLS:
        print(f"Building {symbol} {start} → {end}")
        reports = build_symbol_datasets(symbol, start=start, end=end, force=False)
        for interval, q in reports.items():
            print(
                f"  {interval}: rows={q.rows} missing={q.missing_candles} ok={q.ok}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
