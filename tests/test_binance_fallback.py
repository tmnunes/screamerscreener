"""Tests for Binance OHLC fallback + FreeCryptoAPI quote parsing."""

from backend.data.binance_ohlc import binance_pair
from backend.data.freecryptoapi import parse_ohlc_payload, parse_quote_payload


def test_binance_pair_mapping() -> None:
    assert binance_pair("BTC") == "BTCUSDT"
    assert binance_pair("eth") == "ETHUSDT"
    assert binance_pair("USDT") is None


def test_parse_getdata_symbols_shape() -> None:
    payload = {
        "status": "success",
        "symbols": [
            {
                "symbol": "BTC",
                "last": "77326.42",
                "daily_change_percentage": "0.0074624307995394",
                "date": "2026-08-23 21:35:23",
            }
        ],
    }
    quotes = parse_quote_payload(payload)
    assert len(quotes) == 1
    assert quotes[0]["symbol"] == "BTC"
    assert abs(quotes[0]["price"] - 77326.42) < 1e-6
    assert abs(quotes[0]["change_24h"] - 0.0074624307995394) < 1e-12


def test_parse_ohlc_empty_on_plan_error_body() -> None:
    rows = parse_ohlc_payload(
        {"status": False, "error": "Your plan does not include historical data."}
    )
    assert rows == []
