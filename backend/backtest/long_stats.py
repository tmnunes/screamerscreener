"""Aggregate min / max / avg forward returns for LONG triggers."""

from __future__ import annotations

from typing import Any

from backend.backtest.performance import STATS_HORIZONS


def _horizon_stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"min": None, "max": None, "avg": None, "count": 0}
    return {
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
        "count": len(values),
    }


def aggregate_horizons(
    samples: list[dict[str, Any]],
    *,
    horizons: tuple[int, ...] = STATS_HORIZONS,
) -> dict[str, dict[str, float | int | None]]:
    """samples: list of performance dicts (or objects with return_*d keys)."""
    out: dict[str, dict[str, float | int | None]] = {}
    for offset in horizons:
        key = f"return_{offset}d"
        values = [
            float(s[key])
            for s in samples
            if s.get(key) is not None
        ]
        out[f"{offset}d"] = _horizon_stats(values)
    return out


def summarize_long_performance(
    rows: list[dict[str, Any]],
    *,
    horizons: tuple[int, ...] = STATS_HORIZONS,
) -> dict[str, Any]:
    """
    rows: enriched trigger-like dicts with performance + optional ticker/name.

    Only LONG rows should be passed. Each horizon uses only signals mature
    enough to have that return (nulls excluded from min/max/avg).
    """
    perfs = [r.get("performance") or {} for r in rows]
    overall = aggregate_horizons(perfs, horizons=horizons)

    by_ticker: dict[str, list[dict[str, Any]]] = {}
    meta_by_ticker: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = row.get("ticker") or "?"
        by_ticker.setdefault(ticker, []).append(row.get("performance") or {})
        meta_by_ticker[ticker] = {
            "ticker": ticker,
            "name": row.get("name"),
            "instrument_id": row.get("instrument_id"),
        }

    by_stock = []
    for ticker, samples in sorted(by_ticker.items()):
        meta = meta_by_ticker[ticker]
        by_stock.append(
            {
                **meta,
                "long_count": len(samples),
                "horizons": aggregate_horizons(samples, horizons=horizons),
            }
        )

    return {
        "trigger_type": "LONG",
        "long_count": len(rows),
        "horizons": overall,
        "by_stock": by_stock,
        "note": (
            "Min / max / avg use only LONG signals with enough future trading "
            "days for that horizon (nulls excluded)."
        ),
    }
