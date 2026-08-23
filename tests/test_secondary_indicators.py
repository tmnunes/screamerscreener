"""Unit tests for secondary indicator math (informational — no trigger coupling)."""

from __future__ import annotations

from backend.indicators.secondary import calculate_secondary_indicators
from backend.indicators.series_math import ema_length_series, sma_series
from backend.signals.vortex_triggers import TriggerType, detect_triggers


def test_sma_basic() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    out = sma_series(values, 3)
    assert out[0] is None
    assert out[1] is None
    assert out[2] == 2.0
    assert out[4] == 4.0


def test_ema_length_matches_alpha() -> None:
    values = [10.0, 11.0, 12.0]
    out = ema_length_series(values, 2)
    # alpha = 2/(2+1) = 2/3
    assert out[0] == 10.0
    assert abs(out[1] - (2 / 3 * 11 + 1 / 3 * 10)) < 1e-12


def test_secondary_rsi_bounds() -> None:
    closes = [float(i) for i in range(1, 40)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    volumes = [1000.0] * len(closes)
    dates = [f"2026-02-{i:02d}" for i in range(1, len(closes) + 1)]
    rows = calculate_secondary_indicators(dates, highs, lows, closes, volumes)
    last = rows[-1]
    assert last.rsi14 is not None
    assert 50 < last.rsi14 <= 100
    assert last.ema20 is not None
    assert last.relative_volume is not None


def test_secondary_does_not_affect_triggers() -> None:
    """Sanity: secondary calc and trigger detect are independent APIs."""
    closes = [10.0, 10.0, 10.0, 10.0]
    basis = [10.0] * 4
    upper = [1.0, 1.0, 3.0, 4.0]
    lower = [2.0, 2.0, 2.0, 2.0]
    events = detect_triggers(closes, basis, upper, lower)
    assert len([e for e in events if e.trigger_type == TriggerType.LONG]) == 1

    # Running secondary on unrelated data must not change the above assertion path
    rows = calculate_secondary_indicators(
        ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
        [11, 12, 13, 14],
        [9, 10, 11, 12],
        closes,
        [100, 100, 100, 100],
    )
    assert len(rows) == 4
    events2 = detect_triggers(closes, basis, upper, lower)
    assert [e.index for e in events] == [e.index for e in events2]


def test_breakout_flags() -> None:
    n = 60
    closes = [100.0] * n
    closes[-1] = 200.0  # breakout on last bar
    highs = list(closes)
    lows = [c - 1 for c in closes]
    volumes = [1.0] * n
    dates = [f"2025-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}" for i in range(n)]
    rows = calculate_secondary_indicators(dates, highs, lows, closes, volumes)
    assert rows[-1].breakout_20d is True
    assert rows[-1].breakout_50d is True
