"""Unit tests for research data aggregation and causal indicators."""

from __future__ import annotations

import pandas as pd

from backend.research.data.aggregate import aggregate_ohlcv
from backend.research.indicators import core as ind
from backend.research.backtest.engine import run_backtest
from backend.research.strategies.catalog import sig_ema_cross


def _fake_5m(n: int = 120) -> pd.DataFrame:
    # 10 hours of synthetic 5m bars
    ts = pd.date_range("2024-10-01", periods=n, freq="5min", tz="UTC")
    close = pd.Series(range(n), dtype=float) + 100
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open_time": (ts.asi8 // 10**6).astype("int64"),
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 10.0,
            "trades": 5,
            "taker_buy_base": 4.0,
        }
    )
    return df


def test_aggregate_15m_ohlcv_rules() -> None:
    df = _fake_5m(12)
    agg = aggregate_ohlcv(df, "15m")
    assert len(agg) == 4
    first = agg.iloc[0]
    assert first["open"] == df.iloc[0]["open"]
    assert first["close"] == df.iloc[2]["close"]
    assert first["high"] == df.iloc[:3]["high"].max()
    assert first["low"] == df.iloc[:3]["low"].min()
    assert first["volume"] == 30.0


def test_rsi_no_lookahead_prefix() -> None:
    df = _fake_5m(80)
    full = ind.rsi(df["close"], 14)
    prefix = ind.rsi(df["close"].iloc[:50], 14)
    assert abs(full.iloc[49] - prefix.iloc[49]) < 1e-9


def test_backtest_long_only_smoke() -> None:
    df = _fake_5m(200)
    sig = sig_ema_cross(df)
    result = run_backtest(df, sig, stop_atr_mult=None)
    assert result.metrics.get("trades", 0) >= 0
    assert len(result.equity_curve) == len(df)
