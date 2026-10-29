"""Automated OHLCV quality checks for research datasets."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(slots=True)
class QualityReport:
    symbol: str
    interval: str
    rows: int
    start: str | None
    end: str | None
    duplicate_timestamps: int
    out_of_order: int
    missing_candles: int
    invalid_ohlc: int
    non_positive_price: int
    negative_volume: int
    expected_bars: int | None
    gap_ratio: float | None

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def ok(self) -> bool:
        return (
            self.duplicate_timestamps == 0
            and self.out_of_order == 0
            and self.invalid_ohlc == 0
            and self.non_positive_price == 0
            and self.negative_volume == 0
            and (self.gap_ratio is None or self.gap_ratio < 0.02)
        )


INTERVAL_MS = {
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 60 * 60_000,
}


def validate_ohlcv(df: pd.DataFrame, *, symbol: str, interval: str) -> QualityReport:
    if df.empty:
        return QualityReport(
            symbol=symbol,
            interval=interval,
            rows=0,
            start=None,
            end=None,
            duplicate_timestamps=0,
            out_of_order=0,
            missing_candles=0,
            invalid_ohlc=0,
            non_positive_price=0,
            negative_volume=0,
            expected_bars=0,
            gap_ratio=None,
        )

    work = df.copy()
    if "timestamp" not in work.columns:
        work["timestamp"] = pd.to_datetime(work["open_time"], unit="ms", utc=True)
    work = work.sort_values("timestamp")

    dupes = int(work["timestamp"].duplicated().sum())
    out_of_order = int((work["timestamp"].diff().dt.total_seconds().fillna(0) < 0).sum())

    invalid = (
        (work["high"] < work["low"])
        | (work["close"] > work["high"])
        | (work["close"] < work["low"])
        | (work["open"] > work["high"])
        | (work["open"] < work["low"])
    )
    non_pos = (work[["open", "high", "low", "close"]] <= 0).any(axis=1)
    neg_vol = work["volume"] < 0 if "volume" in work.columns else pd.Series(False, index=work.index)

    step = INTERVAL_MS.get(interval)
    missing = 0
    expected = None
    gap_ratio = None
    if step is not None and len(work) >= 2:
        start_ms = int(work["open_time"].iloc[0])
        end_ms = int(work["open_time"].iloc[-1])
        expected = int((end_ms - start_ms) / step) + 1
        diffs = work["open_time"].diff().dropna()
        missing = int(((diffs / step) - 1).clip(lower=0).sum())
        gap_ratio = float(missing) / float(expected) if expected else None

    start = str(work["timestamp"].iloc[0])
    end = str(work["timestamp"].iloc[-1])
    return QualityReport(
        symbol=symbol,
        interval=interval,
        rows=len(work),
        start=start,
        end=end,
        duplicate_timestamps=dupes,
        out_of_order=out_of_order,
        missing_candles=missing,
        invalid_ohlc=int(invalid.sum()),
        non_positive_price=int(non_pos.sum()),
        negative_volume=int(neg_vol.sum()),
        expected_bars=expected,
        gap_ratio=gap_ratio,
    )
