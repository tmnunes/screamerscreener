"""Tests for Binance OHLC fallback + FreeCryptoAPI quote parsing."""

from datetime import date
from unittest.mock import MagicMock, patch

from backend.data.binance_ohlc import (
    BINANCE_KLINES,
    BINANCE_KLINES_URLS,
    binance_pair,
    fetch_binance_daily,
)
from backend.data.freecryptoapi import parse_ohlc_payload, parse_quote_payload


def test_binance_pair_mapping() -> None:
    assert binance_pair("BTC") == "BTCUSDT"
    assert binance_pair("eth") == "ETHUSDT"
    assert binance_pair("USDT") is None


def test_binance_primary_url_is_public_data_host() -> None:
    assert "data-api.binance.vision" in BINANCE_KLINES
    assert BINANCE_KLINES_URLS[0] == BINANCE_KLINES


def test_fetch_binance_daily_skips_451_and_uses_next_host() -> None:
    """api.binance.com geo-blocks many cloud regions with HTTP 451."""
    blocked = MagicMock()
    blocked.status_code = 451
    blocked.is_success = False
    blocked.text = "Service unavailable from a restricted location"

    ok = MagicMock()
    ok.status_code = 200
    ok.is_success = True
    ok.json.return_value = [
        [
            1787616000000,
            "100",
            "110",
            "90",
            "105",
            "12.5",
            1787702399999,
        ]
    ]

    client = MagicMock()
    client.get.side_effect = [blocked, ok]
    client.__enter__.return_value = client
    client.__exit__.return_value = False

    with patch("backend.data.binance_ohlc.httpx.Client", return_value=client):
        candles = fetch_binance_daily(
            "ADA",
            from_date=date(2026, 8, 25),
            to_date=date(2026, 8, 25),
        )

    assert len(candles) == 1
    assert candles[0]["date"] == "2026-08-25"
    assert candles[0]["close"] == 105.0
    assert client.get.call_count == 2
    assert "data-api.binance.vision" in client.get.call_args_list[0].args[0]


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
