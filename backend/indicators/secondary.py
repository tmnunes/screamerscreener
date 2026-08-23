"""Secondary indicators — informational only.

These values MUST NOT create, block, or modify Vortex LONG / SHORT / STOP triggers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend.indicators.series_math import (
    ema_length_series,
    rolling_max,
    rolling_min,
    rma_series,
    sma_series,
    true_range_series,
)


@dataclass(slots=True)
class SecondaryIndicatorRow:
    date: str
    ema20: float | None = None
    ema50: float | None = None
    ema200: float | None = None
    sma200: float | None = None
    adx14: float | None = None
    rsi14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    roc14: float | None = None
    stoch_k: float | None = None
    stoch_d: float | None = None
    volume_sma20: float | None = None
    relative_volume: float | None = None
    obv: float | None = None
    atr14: float | None = None
    atr_pct: float | None = None
    bb_width: float | None = None
    breakout_20d: bool | None = None
    breakout_50d: bool | None = None
    dist_52w_high: float | None = None

    def as_db_row(self, instrument_id: str) -> dict[str, Any]:
        data = asdict(self)
        data["instrument_id"] = instrument_id
        return data


def _rsi(closes: list[float], length: int = 14) -> list[float | None]:
    if len(closes) < 2:
        return [None] * len(closes)
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = rma_series(gains, length)
    avg_loss = rma_series(losses, length)
    out: list[float | None] = []
    for g, l in zip(avg_gain, avg_loss):
        if g is None or l is None:
            out.append(None)
        elif l == 0:
            out.append(100.0)
        else:
            rs = g / l
            out.append(100.0 - (100.0 / (1.0 + rs)))
    return out


def _macd(
    closes: list[float],
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    ema12 = ema_length_series(closes, 12)
    ema26 = ema_length_series(closes, 26)
    line = [a - b for a, b in zip(ema12, ema26)]
    # Signal needs enough history; seed EMA on full MACD line (same recursive style)
    signal = ema_length_series(line, 9)
    hist = [l - s for l, s in zip(line, signal)]
    # Mark early bars as None until EMA26 is meaningful (~26 bars)
    macd_out: list[float | None] = []
    sig_out: list[float | None] = []
    hist_out: list[float | None] = []
    for i in range(len(closes)):
        if i < 25:
            macd_out.append(None)
            sig_out.append(None)
            hist_out.append(None)
        else:
            macd_out.append(line[i])
            sig_out.append(signal[i])
            hist_out.append(hist[i])
    return macd_out, sig_out, hist_out


def _roc(closes: list[float], length: int = 14) -> list[float | None]:
    out: list[float | None] = []
    for i, c in enumerate(closes):
        if i < length or closes[i - length] == 0:
            out.append(None)
        else:
            out.append((c / closes[i - length] - 1.0) * 100.0)
    return out


def _stochastic(
    highs: list[float], lows: list[float], closes: list[float], length: int = 14
) -> tuple[list[float | None], list[float | None]]:
    hh = rolling_max(highs, length)
    ll = rolling_min(lows, length)
    k_raw: list[float | None] = []
    for i, c in enumerate(closes):
        if hh[i] is None or ll[i] is None:
            k_raw.append(None)
            continue
        span = hh[i] - ll[i]  # type: ignore[operator]
        if span == 0:
            k_raw.append(50.0)
        else:
            k_raw.append(100.0 * (c - ll[i]) / span)  # type: ignore[operator]

    # %D = SMA3 of %K
    k_filled = [0.0 if v is None else v for v in k_raw]
    d_sma = sma_series(k_filled, 3)
    d_out: list[float | None] = []
    for i, k in enumerate(k_raw):
        if k is None or d_sma[i] is None or i < length:
            d_out.append(None)
        else:
            d_out.append(d_sma[i])
    k_out = [None if i < length - 1 else k_raw[i] for i in range(len(k_raw))]
    return k_out, d_out


def _adx(
    highs: list[float], lows: list[float], closes: list[float], length: int = 14
) -> list[float | None]:
    n = len(closes)
    if n < 2:
        return [None] * n

    plus_dm = [0.0]
    minus_dm = [0.0]
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)

    tr = true_range_series(highs, lows, closes)
    atr = rma_series(tr, length)
    plus_di_rma = rma_series(plus_dm, length)
    minus_di_rma = rma_series(minus_dm, length)

    dx: list[float] = []
    for i in range(n):
        a = atr[i]
        p = plus_di_rma[i]
        m = minus_di_rma[i]
        if a is None or p is None or m is None or a == 0:
            dx.append(0.0)
            continue
        plus_di = 100.0 * p / a
        minus_di = 100.0 * m / a
        denom = plus_di + minus_di
        dx.append(0.0 if denom == 0 else 100.0 * abs(plus_di - minus_di) / denom)

    adx = rma_series(dx, length)
    # ADX is meaningful after ~2*length bars
    out: list[float | None] = []
    for i, v in enumerate(adx):
        if i < 2 * length - 1 or v is None:
            out.append(None)
        else:
            out.append(v)
    return out


def _obv(closes: list[float], volumes: list[float]) -> list[float]:
    out: list[float] = []
    running = 0.0
    for i, c in enumerate(closes):
        if i == 0:
            out.append(0.0)
            continue
        if c > closes[i - 1]:
            running += volumes[i]
        elif c < closes[i - 1]:
            running -= volumes[i]
        out.append(running)
    return out


def _bollinger_width(closes: list[float], length: int = 20, mult: float = 2.0) -> list[float | None]:
    mid = sma_series(closes, length)
    out: list[float | None] = []
    for i in range(len(closes)):
        if mid[i] is None or mid[i] == 0:
            out.append(None)
            continue
        window = closes[i + 1 - length : i + 1]
        mean = mid[i]
        assert mean is not None
        var = sum((x - mean) ** 2 for x in window) / length
        std = var**0.5
        upper = mean + mult * std
        lower = mean - mult * std
        out.append((upper - lower) / mean)
    return out


def calculate_secondary_indicators(
    dates: list[str],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
) -> list[SecondaryIndicatorRow]:
    """Compute all secondary indicators for a daily OHLCV series.

    Does not interact with Vortex triggers in any way.
    """
    n = len(closes)
    if not (len(dates) == len(highs) == len(lows) == len(volumes) == n):
        raise ValueError("all series must have equal length")
    if n == 0:
        return []

    ema20 = ema_length_series(closes, 20)
    ema50 = ema_length_series(closes, 50)
    ema200 = ema_length_series(closes, 200)
    sma200 = sma_series(closes, 200)
    adx14 = _adx(highs, lows, closes, 14)
    rsi14 = _rsi(closes, 14)
    macd, macd_signal, macd_hist = _macd(closes)
    roc14 = _roc(closes, 14)
    stoch_k, stoch_d = _stochastic(highs, lows, closes, 14)

    vol_sma20 = sma_series(volumes, 20)
    relative_volume: list[float | None] = []
    for i, v in enumerate(volumes):
        s = vol_sma20[i]
        if s is None or s == 0:
            relative_volume.append(None)
        else:
            relative_volume.append(v / s)
    obv = _obv(closes, volumes)

    tr = true_range_series(highs, lows, closes)
    atr14 = rma_series(tr, 14)
    atr_pct: list[float | None] = []
    for i, a in enumerate(atr14):
        if a is None or closes[i] == 0 or i < 13:
            atr_pct.append(None)
        else:
            atr_pct.append(100.0 * a / closes[i])

    bb_width = _bollinger_width(closes, 20, 2.0)

    high_20 = rolling_max(highs, 20)
    high_50 = rolling_max(highs, 50)
    high_252 = rolling_max(highs, 252)

    rows: list[SecondaryIndicatorRow] = []
    for i in range(n):
        # Breakout: close breaks above prior N-day high (exclude today from lookback)
        br20: bool | None = None
        br50: bool | None = None
        if i >= 20:
            prior_high_20 = max(highs[i - 20 : i])
            br20 = closes[i] > prior_high_20
        if i >= 50:
            prior_high_50 = max(highs[i - 50 : i])
            br50 = closes[i] > prior_high_50

        dist_52w: float | None = None
        if high_252[i] is not None and high_252[i] != 0:
            dist_52w = closes[i] / high_252[i] - 1.0  # type: ignore[operator]

        rows.append(
            SecondaryIndicatorRow(
                date=dates[i],
                ema20=ema20[i] if i >= 19 else None,
                ema50=ema50[i] if i >= 49 else None,
                ema200=ema200[i] if i >= 199 else None,
                sma200=sma200[i],
                adx14=adx14[i],
                rsi14=rsi14[i],
                macd=macd[i],
                macd_signal=macd_signal[i],
                macd_hist=macd_hist[i],
                roc14=roc14[i],
                stoch_k=stoch_k[i],
                stoch_d=stoch_d[i],
                volume_sma20=vol_sma20[i],
                relative_volume=relative_volume[i],
                obv=obv[i],
                atr14=atr14[i] if i >= 13 else None,
                atr_pct=atr_pct[i],
                bb_width=bb_width[i],
                breakout_20d=br20,
                breakout_50d=br50,
                dist_52w_high=dist_52w,
            )
        )
    return rows
