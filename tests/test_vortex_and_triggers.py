"""Comprehensive unit tests for Vortex math, triggers, and helpers."""

from __future__ import annotations

from backend.backtest.performance import (
    calculate_performance_from_closes,
    performance_from_price_series,
    performance_needs_update,
)
from backend.indicators.vortex_bands import (
    alpha_from_length,
    calculate_vortex_bands,
    ema_series,
    hlc3,
    mnma_series,
)
from backend.signals.vortex_triggers import TriggerType, detect_triggers


def test_hlc3() -> None:
    assert hlc3(10, 4, 7) == 7.0


def test_alpha() -> None:
    assert alpha_from_length(1) == 1.0
    assert abs(alpha_from_length(47) - (2 / 48)) < 1e-12


def test_ema_recursive_seed() -> None:
    alpha = 0.5
    values = [10.0, 12.0, 11.0]
    out = ema_series(values, alpha)
    assert out[0] == 10.0
    assert out[1] == 0.5 * 12 + 0.5 * 10
    assert out[2] == 0.5 * 11 + 0.5 * out[1]


def test_mnma_matches_formula() -> None:
    length = 3
    alpha = 2 / (length + 1)
    src = [1.0, 2.0, 3.0, 4.0]
    ema1 = ema_series(src, alpha)
    ema2 = ema_series(ema1, alpha)
    expected = [((2 - alpha) * a - b) / (1 - alpha) for a, b in zip(ema1, ema2)]
    assert mnma_series(src, length) == expected


def test_basis_upper_lower() -> None:
    highs = [11.0, 12.0, 13.0, 14.0, 15.0]
    lows = [9.0, 10.0, 11.0, 12.0, 13.0]
    closes = [10.0, 11.0, 12.0, 13.0, 14.0]
    rows = calculate_vortex_bands(highs, lows, closes, length=3, mult=2.0)
    assert len(rows) == 5
    for row in rows:
        assert abs((row.upper - row.basis) - (row.basis - row.lower)) < 1e-9


def test_long_crossover_event() -> None:
    # Craft upper/lower so crossover happens only at index 2
    closes = [10.0, 10.0, 10.0, 10.0, 10.0]
    basis = [10.0, 10.0, 10.0, 10.0, 10.0]
    upper = [1.0, 1.0, 3.0, 4.0, 5.0]
    lower = [2.0, 2.0, 2.0, 2.0, 2.0]
    events = detect_triggers(closes, basis, upper, lower)
    longs = [e for e in events if e.trigger_type == TriggerType.LONG]
    assert len(longs) == 1
    assert longs[0].index == 2


def test_short_crossover_event() -> None:
    closes = [10.0, 10.0, 10.0, 10.0]
    basis = [10.0] * 4
    upper = [2.0, 2.0, 2.0, 2.0]
    lower = [1.0, 1.0, 3.0, 4.0]
    events = detect_triggers(closes, basis, upper, lower)
    shorts = [e for e in events if e.trigger_type == TriggerType.SHORT]
    assert len(shorts) == 1
    assert shorts[0].index == 2


def test_stop_crossover_event() -> None:
    closes = [12.0, 11.0, 9.0, 8.0]
    basis = [10.0, 10.0, 10.0, 10.0]
    upper = [15.0] * 4
    lower = [5.0] * 4
    events = detect_triggers(closes, basis, upper, lower)
    stops = [e for e in events if e.trigger_type == TriggerType.STOP]
    assert len(stops) == 1
    assert stops[0].index == 2


def test_upper_above_lower_only_one_long() -> None:
    closes = [10.0] * 6
    basis = [10.0] * 6
    upper = [1, 1, 3, 4, 5, 6]
    lower = [2, 2, 2, 2, 2, 2]
    events = detect_triggers(closes, basis, [float(x) for x in upper], [float(x) for x in lower])
    assert len([e for e in events if e.trigger_type == TriggerType.LONG]) == 1


def test_lower_above_upper_only_one_short() -> None:
    closes = [10.0] * 6
    basis = [10.0] * 6
    upper = [2.0] * 6
    lower = [1, 1, 3, 4, 5, 6]
    events = detect_triggers(closes, basis, upper, [float(x) for x in lower])
    assert len([e for e in events if e.trigger_type == TriggerType.SHORT]) == 1


def test_close_below_basis_only_one_stop() -> None:
    closes = [12, 11, 9, 8, 7, 6]
    basis = [10.0] * 6
    upper = [20.0] * 6
    lower = [0.0] * 6
    events = detect_triggers([float(x) for x in closes], basis, upper, lower)
    assert len([e for e in events if e.trigger_type == TriggerType.STOP]) == 1


def test_no_lookahead_trigger_uses_only_past_and_current() -> None:
    closes = [10.0, 10.0, 10.0, 99.0]
    basis = [10.0] * 4
    upper = [1.0, 1.0, 3.0, 3.0]
    lower = [2.0, 2.0, 2.0, 2.0]
    # If calculation wrongly used t+1, a synthetic future spike could change earlier signals.
    # Truncating series at t=2 must yield the same LONG at index 2.
    full = detect_triggers(closes, basis, upper, lower)
    truncated = detect_triggers(closes[:3], basis[:3], upper[:3], lower[:3])
    assert [e.index for e in full if e.trigger_type == TriggerType.LONG] == [2]
    assert [e.index for e in truncated if e.trigger_type == TriggerType.LONG] == [2]


def test_performance_long_short_and_null_horizons() -> None:
    long_perf = calculate_performance_from_closes(
        trigger_type="LONG",
        trigger_price=100.0,
        closes_after=[101.0, 102.0, 103.0],
    )
    assert abs(long_perf.return_1d - 0.01) < 1e-12
    assert abs(long_perf.return_3d - 0.03) < 1e-12
    assert long_perf.return_5d is None

    short_perf = calculate_performance_from_closes(
        trigger_type="SHORT",
        trigger_price=100.0,
        closes_after=[90.0],
    )
    assert abs(short_perf.return_1d - (100 / 90 - 1)) < 1e-12


def test_performance_needs_update_when_partial() -> None:
    perf = {"return_1d": -0.0057, "return_3d": None}
    assert performance_needs_update(perf, future_trading_days=5) is True
    assert performance_needs_update(perf, future_trading_days=1) is False


def test_performance_from_price_series_fills_horizons() -> None:
    prices = [
        {"date": f"2026-01-{d:02d}", "close": 100.0 + d}
        for d in range(1, 11)
    ]
    perf = performance_from_price_series(
        prices,
        trigger_date="2026-01-02",
        trigger_type="LONG",
        trigger_price=102.0,
    )
    assert perf.return_1d is not None
    assert perf.return_3d is not None
    assert perf.return_5d is not None
    assert perf.return_10d is None


def test_idempotent_candle_merge_logic() -> None:
    """Simulate filtering already-stored dates (ingestion idempotency)."""
    existing_last = "2026-01-10"
    incoming = [
        {"date": "2026-01-09", "close": 1},
        {"date": "2026-01-10", "close": 2},
        {"date": "2026-01-11", "close": 3},
    ]
    filtered = [c for c in incoming if c["date"] > existing_last]
    assert [c["date"] for c in filtered] == ["2026-01-11"]
