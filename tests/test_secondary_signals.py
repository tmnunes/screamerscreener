"""Tests for secondary indicator traffic-light scoring."""

from __future__ import annotations

from backend.indicators.secondary_signals import (
    evaluate_secondary_signals,
    summarize_signals,
    IndicatorSignal,
)


def _bullish_row() -> dict:
    return {
        "ema20": 100,
        "ema50": 95,
        "sma200": 90,
        "adx14": 30,
        "rsi14": 62,
        "macd": 1.5,
        "macd_signal": 1.0,
        "macd_hist": 0.5,
        "roc14": 2.5,
        "stoch_k": 70,
        "stoch_d": 60,
        "relative_volume": 1.3,
        "atr_pct": 2.0,
        "breakout_20d": True,
        "breakout_50d": True,
        "dist_52w_high": -0.02,
    }


def test_long_trigger_bullish_secondary_is_green() -> None:
    summary = evaluate_secondary_signals(
        trigger_type="LONG",
        trigger_price=105,
        secondary_row=_bullish_row(),
        market_regime={"spy_above_sma200": True, "qqq_above_sma200": True},
    )
    assert summary is not None
    assert summary.overall == "green"
    assert summary.green > summary.red


def test_short_trigger_bullish_secondary_is_red() -> None:
    summary = evaluate_secondary_signals(
        trigger_type="SHORT",
        trigger_price=105,
        secondary_row=_bullish_row(),
    )
    assert summary is not None
    assert summary.overall == "red"


def test_missing_secondary_returns_none() -> None:
    assert evaluate_secondary_signals(
        trigger_type="LONG", trigger_price=100, secondary_row=None
    ) is None


def test_summarize_neutral_on_mixed() -> None:
    items = [
        IndicatorSignal("a", "A", "TREND", "green", ""),
        IndicatorSignal("b", "B", "TREND", "red", ""),
        IndicatorSignal("c", "C", "TREND", "neutral", ""),
    ]
    summary = summarize_signals(items)
    assert summary.overall == "neutral"
    assert summary.green == 1
    assert summary.red == 1
