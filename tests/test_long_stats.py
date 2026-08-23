"""Tests for LONG performance aggregation stats."""

from backend.backtest.long_stats import aggregate_horizons, summarize_long_performance
from backend.backtest.performance import calculate_performance_from_closes


def test_aggregate_horizons_min_max_avg() -> None:
    samples = [
        {"return_5d": 0.10, "return_10d": 0.20, "return_15d": None},
        {"return_5d": -0.05, "return_10d": 0.00, "return_15d": 0.01},
        {"return_5d": 0.00, "return_10d": None, "return_15d": 0.03},
    ]
    out = aggregate_horizons(samples)
    assert out["5d"]["count"] == 3
    assert abs(float(out["5d"]["min"]) - (-0.05)) < 1e-12
    assert abs(float(out["5d"]["max"]) - 0.10) < 1e-12
    assert abs(float(out["5d"]["avg"]) - (0.10 - 0.05 + 0.0) / 3) < 1e-12
    assert out["10d"]["count"] == 2
    assert out["15d"]["count"] == 2
    assert abs(float(out["15d"]["avg"]) - 0.02) < 1e-12


def test_summarize_long_performance_by_stock() -> None:
    rows = [
        {
            "ticker": "AAA",
            "name": "Aaa Inc",
            "instrument_id": "1",
            "performance": {"return_5d": 0.1, "return_10d": 0.2, "return_15d": 0.3},
        },
        {
            "ticker": "AAA",
            "name": "Aaa Inc",
            "instrument_id": "1",
            "performance": {"return_5d": -0.1, "return_10d": None, "return_15d": None},
        },
        {
            "ticker": "BBB",
            "name": "Bbb Inc",
            "instrument_id": "2",
            "performance": {"return_5d": 0.0, "return_10d": 0.05, "return_15d": 0.1},
        },
    ]
    summary = summarize_long_performance(rows)
    assert summary["trigger_type"] == "LONG"
    assert summary["long_count"] == 3
    assert abs(float(summary["horizons"]["5d"]["avg"]) - 0.0) < 1e-12
    assert len(summary["by_stock"]) == 2
    aaa = next(s for s in summary["by_stock"] if s["ticker"] == "AAA")
    assert aaa["long_count"] == 2
    assert aaa["horizons"]["5d"]["count"] == 2


def test_performance_includes_15d() -> None:
    closes = [101.0 + i for i in range(20)]
    perf = calculate_performance_from_closes(
        trigger_type="LONG",
        trigger_price=100.0,
        closes_after=closes,
    )
    assert perf.return_15d is not None
    assert abs(perf.return_15d - (closes[14] / 100.0 - 1.0)) < 1e-12
