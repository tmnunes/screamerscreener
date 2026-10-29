"""Aggregate native 5m OHLCV into higher timeframes without fabricating gaps."""

from __future__ import annotations

import pandas as pd

INTERVAL_RULES = {
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
}


def aggregate_ohlcv(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Aggregate 5m candles to ``interval`` using standard OHLCV rules.

    Missing source bars are not filled. Incomplete buckets (fewer bars than
    expected for a continuous market) are dropped so gaps stay visible.
    """
    if interval not in INTERVAL_RULES:
        raise ValueError(f"Unsupported interval: {interval}")
    if df.empty:
        return df.copy()

    rule = INTERVAL_RULES[interval]
    expected = {"5m": 1, "15m": 3, "30m": 6, "1h": 12}[interval]

    work = df.copy()
    if "timestamp" not in work.columns:
        work["timestamp"] = pd.to_datetime(work["open_time"], unit="ms", utc=True)
    work = work.set_index("timestamp").sort_index()

    agg: dict[str, str] = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    optional = {
        "quote_volume": "sum",
        "trades": "sum",
        "taker_buy_base": "sum",
        "taker_buy_quote": "sum",
        "open_time": "first",
        "close_time": "last",
    }
    for col, how in optional.items():
        if col in work.columns:
            agg[col] = how

    grouped = work.resample(rule, label="left", closed="left")
    counts = grouped["close"].count()
    out = grouped.agg(agg)
    out = out[counts >= expected]
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out.reset_index()
    if "open_time" not in out.columns or out["open_time"].isna().all():
        out["open_time"] = (out["timestamp"].astype("int64") // 10**6).astype("int64")
    return out


def verify_against_native(
    aggregated: pd.DataFrame,
    native: pd.DataFrame,
    *,
    sample: int = 50,
    atol: float = 1e-6,
) -> dict[str, float | int]:
    """Compare aggregated bars to native provider bars on overlapping timestamps."""
    if aggregated.empty or native.empty:
        return {"compared": 0, "match_rate": 0.0}

    a = aggregated.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
    n = native.copy()
    if "timestamp" not in n.columns:
        n["timestamp"] = pd.to_datetime(n["open_time"], unit="ms", utc=True)
    n = n.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
    common = a.index.intersection(n.index)
    if len(common) == 0:
        return {"compared": 0, "match_rate": 0.0}
    common = common[:sample]
    left = a.loc[common]
    right = n.loc[common]
    close_ok = (left["close"] - right["close"]).abs() <= atol * (1 + right["close"].abs())
    high_ok = (left["high"] - right["high"]).abs() <= atol * (1 + right["high"].abs())
    low_ok = (left["low"] - right["low"]).abs() <= atol * (1 + right["low"].abs())
    open_ok = (left["open"] - right["open"]).abs() <= atol * (1 + right["open"].abs())
    matches = (close_ok & high_ok & low_ok & open_ok).sum()
    return {
        "compared": int(len(common)),
        "matches": int(matches),
        "match_rate": float(matches) / float(len(common)),
    }
