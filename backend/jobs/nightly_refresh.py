"""CLI entrypoints for scheduled refresh (Render Cron / local).

Examples:
  python -m backend.jobs.nightly_refresh stocks
  python -m backend.jobs.nightly_refresh crypto
  python -m backend.jobs.nightly_refresh all
"""

from __future__ import annotations

import argparse
import logging
import sys

from backend.api.asset_pipelines import refresh_crypto, refresh_stocks

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Nightly ScreamerScreener refresh")
    parser.add_argument(
        "target",
        choices=["stocks", "crypto", "all"],
        help="Which universe to refresh",
    )
    args = parser.parse_args()

    try:
        if args.target in ("stocks", "all"):
            print("=== Refresh STOCKS ===")
            detail = refresh_stocks()
            print(detail.get("status"), detail.get("asset_type"))
        if args.target in ("crypto", "all"):
            print("=== Refresh CRYPTO ===")
            detail = refresh_crypto()
            print(detail.get("status"), detail.get("asset_type"))
        print("Nightly refresh completed")
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
