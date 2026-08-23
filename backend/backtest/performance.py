"""Trigger forward-return performance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PerformanceResult:
    return_1d: float | None
    return_3d: float | None
    return_5d: float | None
    return_10d: float | None
    return_15d: float | None
    return_20d: float | None
    max_favorable_return: float | None
    max_adverse_return: float | None


def _signed_return(trigger_type: str, trigger_price: float, future_close: float) -> float:
    if trigger_price == 0:
        raise ValueError("trigger_price cannot be zero")
    if trigger_type == "LONG":
        return future_close / trigger_price - 1.0
    if trigger_type == "SHORT":
        return trigger_price / future_close - 1.0
    return future_close / trigger_price - 1.0


def calculate_performance_from_closes(
    *,
    trigger_type: str,
    trigger_price: float,
    closes_after: list[float],
) -> PerformanceResult:
    """closes_after[0] = close at t+1 trading day, [1]=t+2, ..."""

    def at(offset: int) -> float | None:
        idx = offset - 1
        if idx < 0 or idx >= len(closes_after):
            return None
        return _signed_return(trigger_type, trigger_price, closes_after[idx])

    path_returns = [
        _signed_return(trigger_type, trigger_price, c) for c in closes_after[:20]
    ]
    max_fav = max(path_returns) if path_returns else None
    max_adv = min(path_returns) if path_returns else None

    return PerformanceResult(
        return_1d=at(1),
        return_3d=at(3),
        return_5d=at(5),
        return_10d=at(10),
        return_15d=at(15),
        return_20d=at(20),
        max_favorable_return=max_fav,
        max_adverse_return=max_adv,
    )


def performance_from_price_series(
    prices: list[dict[str, Any]],
    *,
    trigger_date: str,
    trigger_type: str,
    trigger_price: float,
) -> PerformanceResult:
    """Compute performance from ordered daily prices (must include trigger_date)."""
    date_to_idx = {p["date"]: i for i, p in enumerate(prices)}
    idx = date_to_idx.get(trigger_date)
    if idx is None:
        return PerformanceResult(None, None, None, None, None, None, None, None)

    closes_after = [float(p["close"]) for p in prices[idx + 1 :]]
    return calculate_performance_from_closes(
        trigger_type=trigger_type,
        trigger_price=float(trigger_price),
        closes_after=closes_after,
    )


def performance_to_row(trigger_id: str, perf: PerformanceResult) -> dict[str, Any]:
    from datetime import datetime, timezone

    return {
        "trigger_id": trigger_id,
        "return_1d": perf.return_1d,
        "return_3d": perf.return_3d,
        "return_5d": perf.return_5d,
        "return_10d": perf.return_10d,
        "return_15d": perf.return_15d,
        "return_20d": perf.return_20d,
        "max_favorable_return": perf.max_favorable_return,
        "max_adverse_return": perf.max_adverse_return,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }


HORIZON_OFFSETS = (1, 3, 5, 10, 15, 20)
STATS_HORIZONS = (5, 10, 15)


def future_trading_days_available(
    prices: list[dict[str, Any]], trigger_date: str
) -> int:
    date_to_idx = {p["date"]: i for i, p in enumerate(prices)}
    idx = date_to_idx.get(trigger_date)
    if idx is None:
        return 0
    return max(0, len(prices) - idx - 1)


def performance_needs_update(
    perf: dict[str, Any] | None, future_trading_days: int
) -> bool:
    """True when stored performance is missing horizons we can now compute."""
    if future_trading_days <= 0:
        return False
    if not perf:
        return True
    for offset in HORIZON_OFFSETS:
        if future_trading_days >= offset and perf.get(f"return_{offset}d") is None:
            return True
    return False


def performance_has_values(perf: dict[str, Any] | None) -> bool:
    if not perf:
        return False
    return any(perf.get(f"return_{offset}d") is not None for offset in HORIZON_OFFSETS)


def performance_as_dict(perf: PerformanceResult) -> dict[str, Any]:
    return asdict(perf)
