"""Trigger forward-return performance."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PerformanceResult:
    return_1d: float | None
    return_3d: float | None
    return_5d: float | None
    return_10d: float | None
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
    # STOP: treat like flat exit — measure absolute move from price is less meaningful;
    # still compute LONG-style for research visibility.
    return future_close / trigger_price - 1.0


def calculate_performance(
    *,
    trigger_type: str,
    trigger_price: float,
    future_closes: list[float | None],
) -> PerformanceResult:
    """future_closes[i] is the close i trading days after the trigger (1-indexed in helpers).

    Pass a list where index 0 unused OR pass closes for offsets 1..N as a dense list
    via the horizons helper below.
    """
    raise NotImplementedError("Use calculate_performance_from_closes")


def calculate_performance_from_closes(
    *,
    trigger_type: str,
    trigger_price: float,
    closes_after: list[float],
) -> PerformanceResult:
    """closes_after[0] = close at t+1, [1]=t+2, ...

    Missing horizons remain None when not enough future bars exist.
    """

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
        return_20d=at(20),
        max_favorable_return=max_fav,
        max_adverse_return=max_adv,
    )
