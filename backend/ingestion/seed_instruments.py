"""Seed market_instruments from the canonical config."""

from __future__ import annotations

import logging

from backend.data.instruments import get_active_instruments
from backend.db import get_supabase

logger = logging.getLogger(__name__)


def seed_instruments() -> int:
    client = get_supabase()
    rows = [i.as_row() for i in get_active_instruments()]
    result = (
        client.table("market_instruments")
        .upsert(rows, on_conflict="ticker")
        .execute()
    )
    count = len(result.data or rows)
    logger.info("Seeded %s instruments", count)
    return count


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    count = seed_instruments()
    print(f"Seeded {count} instruments")


if __name__ == "__main__":
    main()
