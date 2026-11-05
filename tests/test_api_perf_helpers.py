"""Unit tests for API performance helpers (no live Supabase)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.api.deps import (
    clear_api_caches,
    enrich_triggers,
    flatten_trigger_row,
    instrument_ids_for_asset_type,
)
from backend.api.routes import _latest_by_instrument, _prices_last_two


def test_flatten_trigger_row_unwraps_embeds() -> None:
    row = {
        "id": "t1",
        "instrument_id": "i1",
        "date": "2026-11-04",
        "trigger_type": "LONG",
        "trigger_price": 10.0,
        "market_instruments": {
            "ticker": "AAPL",
            "name": "Apple",
            "exchange": "US",
            "country": "USA",
            "currency": "USD",
            "asset_type": "STOCK",
        },
        "trigger_performance": {"return_5d": 0.1},
    }
    flat = flatten_trigger_row(row)
    assert flat["ticker"] == "AAPL"
    assert flat["performance"]["return_5d"] == 0.1
    assert "market_instruments" not in flat


def test_enrich_triggers_skips_performance_refresh_by_default() -> None:
    rows = [
        {
            "id": "t1",
            "instrument_id": "i1",
            "date": "2026-11-04",
            "trigger_type": "LONG",
            "trigger_price": 10.0,
            "ticker": "AAPL",
            "name": "Apple",
            "asset_type": "STOCK",
            "performance": {"return_5d": 0.02},
        }
    ]
    with (
        patch("backend.api.deps._refresh_performance") as refresh,
        patch("backend.api.deps._fetch_secondary_map", return_value={}),
        patch("backend.api.deps._fetch_regime_map", return_value={}),
        patch("backend.api.deps._fetch_crypto_regime_map", return_value={}),
        patch(
            "backend.api.deps.evaluate_secondary_signals",
            return_value=None,
        ),
    ):
        out = enrich_triggers(rows)
        refresh.assert_not_called()
        assert out[0]["ticker"] == "AAPL"
        assert out[0]["performance"]["return_5d"] == 0.02


def test_enrich_triggers_can_skip_secondary() -> None:
    rows = [
        {
            "id": "t1",
            "instrument_id": "i1",
            "date": "2026-11-04",
            "trigger_type": "LONG",
            "trigger_price": 10.0,
            "ticker": "AAPL",
            "performance": {"return_5d": 0.02},
        }
    ]
    with patch("backend.api.deps._fetch_secondary_map") as secondary:
        out = enrich_triggers(rows, include_secondary=False)
        secondary.assert_not_called()
        assert out[0]["secondary_signals"] is None


def test_enrich_triggers_refresh_opt_in() -> None:
    rows = [
        {
            "id": "t1",
            "instrument_id": "i1",
            "date": "2026-11-04",
            "trigger_type": "LONG",
            "trigger_price": 10.0,
            "ticker": "AAPL",
            "performance": None,
        }
    ]
    with (
        patch("backend.api.deps._refresh_performance") as refresh,
        patch("backend.api.deps._fetch_secondary_map", return_value={}),
        patch("backend.api.deps._fetch_regime_map", return_value={}),
        patch("backend.api.deps._fetch_crypto_regime_map", return_value={}),
        patch("backend.api.deps.evaluate_secondary_signals", return_value=None),
    ):
        enrich_triggers(rows, refresh_performance=True, include_secondary=True)
        refresh.assert_called_once()


def test_instrument_ids_cache() -> None:
    clear_api_caches()
    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.execute.return_value = MagicMock(
        data=[{"id": "a"}, {"id": "b"}]
    )

    with patch("backend.api.deps.get_supabase", return_value=client):
        first = instrument_ids_for_asset_type("STOCK")
        second = instrument_ids_for_asset_type("STOCK")

    assert first == ["a", "b"]
    assert second == ["a", "b"]
    assert client.table.call_count == 1


def test_prices_last_two_keeps_newest() -> None:
    rows = [
        {"instrument_id": "i1", "date": "2026-11-01", "close": 1},
        {"instrument_id": "i1", "date": "2026-11-03", "close": 3},
        {"instrument_id": "i1", "date": "2026-11-02", "close": 2},
        {"instrument_id": "i2", "date": "2026-11-03", "close": 9},
    ]
    out = _prices_last_two(rows)
    assert [r["date"] for r in out["i1"]] == ["2026-11-03", "2026-11-02"]
    assert out["i2"][0]["close"] == 9


def test_latest_by_instrument() -> None:
    rows = [
        {"instrument_id": "i1", "date": "2026-11-01", "rsi14": 40},
        {"instrument_id": "i1", "date": "2026-11-03", "rsi14": 55},
        {"instrument_id": "i2", "date": "2026-11-02", "rsi14": 30},
    ]
    out = _latest_by_instrument(rows)
    assert out["i1"]["rsi14"] == 55
    assert out["i2"]["rsi14"] == 30
