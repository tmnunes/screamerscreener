"""Crypto fallback universe stays Binance-tradeable for free-tier OHLC."""

from backend.data.crypto_universe import CRYPTO_FALLBACK_TOP, get_fallback_top


def test_fallback_top_has_pol_not_matic() -> None:
    tickers = {c.ticker for c in get_fallback_top(25)}
    assert "POL" in tickers
    assert "MATIC" not in tickers


def test_fallback_top_excludes_stables_and_dead_pairs() -> None:
    tickers = {c.ticker for c in CRYPTO_FALLBACK_TOP}
    assert tickers.isdisjoint({"USDT", "USDC", "DAI", "OKB", "XMR"})
    assert len(CRYPTO_FALLBACK_TOP) == 25
