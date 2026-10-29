"""Download Binance USD-M perpetual futures history from data.binance.vision.

Official layout (binance-public-data):
  klines:   .../monthly/klines/{SYMBOL}/{INTERVAL}/{SYMBOL}-{INTERVAL}-{YYYY}-{MM}.zip
  funding:  .../monthly/fundingRate/{SYMBOL}/{SYMBOL}-fundingRate-{YYYY}-{MM}.zip

No API key required. Files are cached under data/research/raw/.
"""

from __future__ import annotations

import io
import logging
import time
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

import httpx
import pandas as pd

from backend.research.config import CACHE_DIR, RAW_DIR, VISION_BASE

logger = logging.getLogger(__name__)

KLINE_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trades",
    "taker_buy_base",
    "taker_buy_quote",
    "ignore",
]

FUNDING_COLUMNS = ["calc_time", "funding_interval_hours", "last_funding_rate"]


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def month_range(start: date, end: date) -> list[tuple[int, int]]:
    """Inclusive calendar months from start through end (month starts)."""
    y, m = start.year, start.month
    out: list[tuple[int, int]] = []
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def latest_complete_month(today: date | None = None) -> date:
    today = today or datetime.now(timezone.utc).date()
    if today.month == 1:
        return date(today.year - 1, 12, 1)
    return date(today.year, today.month - 1, 1)


def _raw_path(kind: str, symbol: str, interval: str | None, year: int, month: int) -> Path:
    if kind == "klines":
        assert interval is not None
        return (
            RAW_DIR
            / "klines"
            / symbol
            / interval
            / f"{symbol}-{interval}-{year:04d}-{month:02d}.csv"
        )
    return RAW_DIR / "funding" / symbol / f"{symbol}-fundingRate-{year:04d}-{month:02d}.csv"


def _vision_url(kind: str, symbol: str, interval: str | None, year: int, month: int) -> str:
    ym = f"{year:04d}-{month:02d}"
    if kind == "klines":
        assert interval is not None
        name = f"{symbol}-{interval}-{ym}.zip"
        return f"{VISION_BASE}/klines/{symbol}/{interval}/{name}"
    name = f"{symbol}-fundingRate-{ym}.zip"
    return f"{VISION_BASE}/fundingRate/{symbol}/{name}"


def _download_zip_csv(url: str, *, timeout: float = 120.0, retries: int = 4) -> bytes | None:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(url)
            if resp.status_code in {403, 404}:
                logger.warning("Unavailable (%s): %s", resp.status_code, url)
                return None
            if resp.status_code in {429, 503}:
                sleep_s = 2 ** attempt
                logger.warning("Rate limited (%s) — sleep %ss", resp.status_code, sleep_s)
                time.sleep(sleep_s)
                continue
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                names = [n for n in zf.namelist() if n.endswith(".csv")]
                if not names:
                    raise RuntimeError(f"No CSV in zip: {url}")
                return zf.read(names[0])
        except Exception as exc:  # noqa: BLE001 — resumable download loop
            last_err = exc
            sleep_s = 2 ** attempt
            logger.warning("Download failed (%s) attempt %s: %s", url, attempt + 1, exc)
            time.sleep(sleep_s)
    if last_err:
        logger.error("Giving up on %s: %s", url, last_err)
    return None


def fetch_month_klines(
    symbol: str,
    interval: str,
    year: int,
    month: int,
    *,
    force: bool = False,
    download: bool = True,
) -> Path | None:
    ensure_dirs()
    dest = _raw_path("klines", symbol, interval, year, month)
    if dest.exists() and not force:
        return dest
    if not download:
        return None
    url = _vision_url("klines", symbol, interval, year, month)
    logger.info("Downloading %s", url)
    raw = _download_zip_csv(url)
    if raw is None:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    return dest


def fetch_month_funding(
    symbol: str,
    year: int,
    month: int,
    *,
    force: bool = False,
    download: bool = True,
) -> Path | None:
    ensure_dirs()
    dest = _raw_path("funding", symbol, None, year, month)
    if dest.exists() and not force:
        return dest
    if not download:
        return None
    url = _vision_url("funding", symbol, None, year, month)
    logger.info("Downloading %s", url)
    raw = _download_zip_csv(url)
    if raw is None:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    return dest


def _read_kline_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, header=None)
    # Some archives include a header row
    if str(df.iloc[0, 0]).lower().startswith("open"):
        df = pd.read_csv(path)
        df.columns = [c.strip() for c in df.columns]
        rename = {
            "open_time": "open_time",
            "Open time": "open_time",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "close_time": "close_time",
            "quote_volume": "quote_volume",
            "Quote asset volume": "quote_volume",
            "count": "trades",
            "Number of trades": "trades",
            "taker_buy_base": "taker_buy_base",
            "taker_buy_volume": "taker_buy_base",
            "Taker buy base asset volume": "taker_buy_base",
            "taker_buy_quote": "taker_buy_quote",
            "taker_buy_quote_volume": "taker_buy_quote",
            "Taker buy quote asset volume": "taker_buy_quote",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    else:
        n = min(len(df.columns), len(KLINE_COLUMNS))
        df = df.iloc[:, :n]
        df.columns = KLINE_COLUMNS[:n]
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("open_time", "close_time", "trades"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("quote_volume", "taker_buy_base", "taker_buy_quote"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _read_funding_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, header=None)
    if str(df.iloc[0, 0]).lower().startswith("calc") or "time" in str(df.iloc[0, 0]).lower():
        df = pd.read_csv(path)
        df.columns = [c.strip() for c in df.columns]
        rename = {
            "calc_time": "funding_time",
            "calcTime": "funding_time",
            "fundingTime": "funding_time",
            "last_funding_rate": "funding_rate",
            "lastFundingRate": "funding_rate",
            "fundingRate": "funding_rate",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    else:
        # vision format: calc_time, funding_interval_hours, last_funding_rate
        cols = list(df.columns)
        if len(cols) >= 3:
            df = df.iloc[:, :3]
            df.columns = ["funding_time", "funding_interval_hours", "funding_rate"]
        else:
            df.columns = ["funding_time", "funding_rate"][: len(df.columns)]
    df["funding_time"] = pd.to_numeric(df["funding_time"], errors="coerce")
    df["funding_rate"] = pd.to_numeric(df["funding_rate"], errors="coerce")
    return df.dropna(subset=["funding_time", "funding_rate"])


def load_klines(
    symbol: str,
    interval: str,
    months: Iterable[tuple[int, int]],
    *,
    force_download: bool = False,
    download: bool = True,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year, month in months:
        path = fetch_month_klines(
            symbol,
            interval,
            year,
            month,
            force=force_download,
            download=download,
        )
        if path is None:
            logger.warning("Missing klines %s %s %04d-%02d", symbol, interval, year, month)
            continue
        frames.append(_read_kline_csv(path))
    if not frames:
        return pd.DataFrame(columns=KLINE_COLUMNS)
    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["open_time", "open", "high", "low", "close"])
    df = df.drop_duplicates(subset=["open_time"], keep="last")
    df = df.sort_values("open_time").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df


def load_funding(
    symbol: str,
    months: Iterable[tuple[int, int]],
    *,
    force_download: bool = False,
    download: bool = True,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year, month in months:
        path = fetch_month_funding(
            symbol, year, month, force=force_download, download=download
        )
        if path is None:
            logger.warning("Missing funding %s %04d-%02d", symbol, year, month)
            continue
        frames.append(_read_funding_csv(path))
    if not frames:
        return pd.DataFrame(columns=["funding_time", "funding_rate"])
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["funding_time"], keep="last")
    df = df.sort_values("funding_time").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["funding_time"], unit="ms", utc=True)
    return df


def download_universe(
    symbols: Iterable[str],
    *,
    start: date,
    end: date | None = None,
    interval: str = "5m",
    include_funding: bool = True,
    force: bool = False,
) -> dict[str, dict[str, Path | None]]:
    """Download monthly archives for symbols. Returns path map for diagnostics."""
    end = end or latest_complete_month()
    months = month_range(date(start.year, start.month, 1), date(end.year, end.month, 1))
    result: dict[str, dict[str, Path | None]] = {}
    for symbol in symbols:
        result[symbol] = {}
        for y, m in months:
            key = f"{interval}:{y:04d}-{m:02d}"
            result[symbol][key] = fetch_month_klines(symbol, interval, y, m, force=force)
            if include_funding:
                fkey = f"funding:{y:04d}-{m:02d}"
                result[symbol][fkey] = fetch_month_funding(symbol, y, m, force=force)
    return result
