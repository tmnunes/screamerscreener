"""Normalized dataset cache (parquet) separate from raw vision CSVs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from backend.research.config import NORMALIZED_DIR
from backend.research.data.aggregate import aggregate_ohlcv, verify_against_native
from backend.research.data.download import (
    latest_complete_month,
    load_funding,
    load_klines,
    month_range,
)
from backend.research.data.quality import QualityReport, validate_ohlcv


@dataclass(slots=True)
class DatasetMeta:
    symbol: str
    interval: str
    start: str
    end: str
    rows: int
    source: str
    quality: dict
    aggregation_check: dict | None = None


def _paths(symbol: str, interval: str) -> tuple[Path, Path]:
    base = NORMALIZED_DIR / symbol
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{interval}.parquet", base / f"{interval}.meta.json"


def save_dataset(df: pd.DataFrame, meta: DatasetMeta) -> Path:
    path, meta_path = _paths(meta.symbol, meta.interval)
    df.to_parquet(path, index=False)
    meta_path.write_text(json.dumps(asdict(meta), indent=2))
    return path


def load_dataset(symbol: str, interval: str) -> tuple[pd.DataFrame, DatasetMeta | None]:
    """Prefer research DB; fall back to parquet cache."""
    from backend.research import db as research_db

    df = research_db.load_candles(symbol, interval)
    if not df.empty:
        cov = research_db.candle_coverage(symbol, interval)
        meta = DatasetMeta(
            symbol=symbol,
            interval=interval,
            start=str(cov.get("start") or ""),
            end=str(cov.get("end") or ""),
            rows=int(cov.get("rows") or len(df)),
            source="research_db",
            quality={},
        )
        return df, meta

    path, meta_path = _paths(symbol, interval)
    if not path.exists():
        return pd.DataFrame(), None
    df = pd.read_parquet(path)
    meta = None
    if meta_path.exists():
        raw = json.loads(meta_path.read_text())
        meta = DatasetMeta(**raw)
    return df, meta


def load_funding_normalized(symbol: str) -> pd.DataFrame:
    from backend.research import db as research_db

    df = research_db.load_funding(symbol)
    if not df.empty:
        return df
    path = NORMALIZED_DIR / symbol / "funding.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def build_symbol_datasets(
    symbol: str,
    *,
    start: date,
    end: date | None = None,
    force: bool = False,
) -> dict[str, QualityReport]:
    """Download 5m + funding, aggregate HTF, validate, write parquet cache."""
    end = end or latest_complete_month()
    months = month_range(date(start.year, start.month, 1), date(end.year, end.month, 1))

    # Prefer local raw cache; only hit the network when force=True or files missing.
    df5 = load_klines(symbol, "5m", months, force_download=force, download=True)
    reports: dict[str, QualityReport] = {}
    q5 = validate_ohlcv(df5, symbol=symbol, interval="5m")
    reports["5m"] = q5
    if not df5.empty:
        save_dataset(
            df5,
            DatasetMeta(
                symbol=symbol,
                interval="5m",
                start=q5.start or "",
                end=q5.end or "",
                rows=q5.rows,
                source="data.binance.vision futures um monthly klines",
                quality=q5.as_dict(),
            ),
        )
        from backend.research import db as research_db

        n = research_db.upsert_candles(symbol, "5m", df5)
        logger = __import__("logging").getLogger(__name__)
        logger.info("DB upsert %s 5m rows=%s", symbol, n)

    funding = load_funding(symbol, months, force_download=force, download=True)
    if not funding.empty:
        fpath = NORMALIZED_DIR / symbol / "funding.parquet"
        fpath.parent.mkdir(parents=True, exist_ok=True)
        funding.to_parquet(fpath, index=False)
        from backend.research import db as research_db

        research_db.upsert_funding(symbol, funding)

    # Optional native 1h verification — local files only (no network).
    native_1h = load_klines(symbol, "1h", months, force_download=False, download=False)
    for interval in ("15m", "30m", "1h"):
        agg = aggregate_ohlcv(df5, interval) if not df5.empty else pd.DataFrame()
        check = None
        if interval == "1h" and not native_1h.empty and not agg.empty:
            n = native_1h.copy()
            n["timestamp"] = pd.to_datetime(n["open_time"], unit="ms", utc=True)
            check = verify_against_native(agg, n)
        q = validate_ohlcv(agg, symbol=symbol, interval=interval)
        reports[interval] = q
        if not agg.empty:
            save_dataset(
                agg,
                DatasetMeta(
                    symbol=symbol,
                    interval=interval,
                    start=q.start or "",
                    end=q.end or "",
                    rows=q.rows,
                    source="aggregated from 5m",
                    quality=q.as_dict(),
                    aggregation_check=check,
                ),
            )
            from backend.research import db as research_db

            research_db.upsert_candles(symbol, interval, agg)
    return reports
