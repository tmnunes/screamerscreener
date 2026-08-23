"""FreeCryptoAPI provider parsing + validation tests (no live network)."""

from backend.backtest.performance import calculate_performance_from_closes
from backend.data.freecryptoapi import (
    parse_ohlc_payload,
    parse_top_payload,
    validate_candle,
)
from backend.indicators.vortex_bands import calculate_vortex_bands
from backend.signals.vortex_triggers import TriggerType, detect_triggers


SAMPLE_OHLC = {
    "data": [
        {
            "date": "2024-01-02",
            "open": 100,
            "high": 110,
            "low": 95,
            "close": 105,
            "volume": 1000,
        },
        {
            "date": "2024-01-01",
            "open": 90,
            "high": 100,
            "low": 88,
            "close": 99,
            "volume": 900,
        },
        # duplicate date — should be ignored
        {
            "date": "2024-01-02",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "volume": 1,
        },
    ]
}


def test_parse_ohlc_sorted_deduped() -> None:
    rows = parse_ohlc_payload(SAMPLE_OHLC)
    assert [r["date"] for r in rows] == ["2024-01-01", "2024-01-02"]
    assert rows[1]["close"] == 105.0
    assert rows[1]["adjusted_close"] is None


def test_validate_candle_flags_bad_ohlc() -> None:
    issues = validate_candle(
        {"open": 10, "high": 9, "low": 8, "close": 8.5, "volume": 1}
    )
    assert "high_lt_low" in issues or "open_outside_range" in issues
    issues2 = validate_candle(
        {"open": 10, "high": 12, "low": 8, "close": 13, "volume": -1}
    )
    assert "close_outside_range" in issues2
    assert "negative_volume" in issues2


def test_parse_top_payload() -> None:
    ranked = parse_top_payload(
        {
            "data": [
                {"symbol": "eth", "name": "Ethereum", "rank": 2, "market_cap": 2},
                {"symbol": "BTC", "name": "Bitcoin", "rank": 1, "market_cap": 1},
            ]
        }
    )
    assert [r["symbol"] for r in ranked] == ["BTC", "ETH"]
    assert ranked[0]["api_symbol"] == "BTC"


def test_vortex_and_triggers_on_crypto_like_series() -> None:
    # Synthetic rising series — same engine as stocks
    n = 80
    closes = [100.0 + i * 0.5 for i in range(n)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    rows = calculate_vortex_bands(
        highs=highs, lows=lows, closes=closes, length=47, mult=1.6
    )
    assert len(rows) == n
    basis = [r.basis for r in rows]
    upper = [r.upper for r in rows]
    lower = [r.lower for r in rows]
    events = detect_triggers(closes, basis, upper, lower)
    assert isinstance(events, list)
    for e in events:
        assert e.trigger_type in {
            TriggerType.LONG,
            TriggerType.SHORT,
            TriggerType.STOP,
        }


def test_crypto_performance_long_short() -> None:
    long_perf = calculate_performance_from_closes(
        trigger_type="LONG",
        trigger_price=100.0,
        closes_after=[101, 102, 103, 104, 105],
    )
    assert abs(long_perf.return_5d - 0.05) < 1e-12
    short_perf = calculate_performance_from_closes(
        trigger_type="SHORT",
        trigger_price=100.0,
        closes_after=[95],
    )
    assert abs(short_perf.return_1d - (100 / 95 - 1)) < 1e-12


def test_refresh_isolation_helpers_default_stock() -> None:
    """list_active_instruments defaults to STOCK — crypto never in stock sync."""
    import inspect

    from backend.ingestion import helpers

    sig = inspect.signature(helpers.list_active_instruments)
    assert sig.parameters["asset_type"].default == "STOCK"

    from backend.indicators.calculate_daily import calculate_for_all

    sig2 = inspect.signature(calculate_for_all)
    assert sig2.parameters["asset_type"].default == "STOCK"
