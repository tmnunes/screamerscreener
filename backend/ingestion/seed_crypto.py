"""Seed / refresh CRYPTO instruments (TOP-N universe)."""

from __future__ import annotations

import logging
from typing import Any

from backend.config import get_settings
from backend.data.crypto_universe import (
    crypto_top_n,
    get_fallback_top,
    ranked_rows_to_configs,
)
from backend.data.freecryptoapi import FreeCryptoAPIProvider
from backend.db import get_supabase

logger = logging.getLogger(__name__)


def _upsert_crypto_rows(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    client = get_supabase()
    client.table("market_instruments").upsert(rows, on_conflict="ticker").execute()
    return len(rows)


def _deactivate_fallen_out(active_tickers: set[str]) -> int:
    """Mark CRYPTO instruments not in current TOP-N as inactive / out of universe."""
    client = get_supabase()
    existing = (
        client.table("market_instruments")
        .select("id,ticker")
        .eq("asset_type", "CRYPTO")
        .execute()
    ).data or []
    fallen = [r for r in existing if r["ticker"] not in active_tickers]
    if not fallen:
        return 0
    for row in fallen:
        client.table("market_instruments").update(
            {
                "active": False,
                "in_top_universe": False,
            }
        ).eq("id", row["id"]).execute()
        logger.info("Crypto %s left TOP-%s — deactivated", row["ticker"], crypto_top_n())
    return len(fallen)


def sync_crypto_universe(
    *,
    provider: FreeCryptoAPIProvider | None = None,
    use_api_ranking: bool = True,
) -> dict[str, Any]:
    """Refresh TOP-N crypto instruments.

    Prefer FreeCryptoAPI /getTop. Fall back to configured CRYPTO_FALLBACK_TOP.
    """
    n = crypto_top_n()
    source = "fallback"
    ranked: list[dict[str, Any]] = []

    if use_api_ranking:
        try:
            p = provider or FreeCryptoAPIProvider()
            ranked = p.get_top(n)[:n]
            if ranked:
                source = "freecryptoapi_getTop"
        except Exception as exc:
            logger.warning("getTop failed (%s) — using fallback universe", exc)

    if not ranked:
        configs = get_fallback_top(n)
        rows = [c.as_row() for c in configs]
        source = "fallback"
    else:
        configs = ranked_rows_to_configs(ranked)[:n]
        rows = []
        for c, raw in zip(configs, ranked):
            row = c.as_row()
            if raw.get("market_cap") is not None:
                row["market_cap"] = raw["market_cap"]
            rows.append(row)

    upserted = _upsert_crypto_rows(rows)
    deactivated = _deactivate_fallen_out({r["ticker"] for r in rows})
    return {
        "top_n": n,
        "source": source,
        "upserted": upserted,
        "deactivated": deactivated,
        "tickers": [r["ticker"] for r in rows],
    }


def seed_crypto_instruments(*, use_api_ranking: bool = False) -> dict[str, Any]:
    """Seed crypto instruments without requiring API (fallback by default)."""
    return sync_crypto_universe(use_api_ranking=use_api_ranking)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # Prefer API if key present
    use_api = bool(get_settings().freecryptoapi_api_key)
    detail = seed_crypto_instruments(use_api_ranking=use_api)
    print(detail)


if __name__ == "__main__":
    main()
