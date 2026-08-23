"""Vortex Bands — faithful Pine Script v4 port.

Pine reference:
    _ema(src, alpha) =>
        out = src
        out := alpha * out + (1 - alpha) * nz(out[1], out)
        out

    _mnma(src, length) =>
        alpha = 2 / (length + 1)
        ema1 = _ema(src, alpha)
        ema2 = _ema(ema1, alpha)
        out = ((2 - alpha) * ema1 - ema2) / (1 - alpha)
        out

    basis = _mnma(src, length)
    dev = mult * _mnma(src - basis, length)
    upper = basis + dev
    lower = basis - dev
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_LENGTH = 47
DEFAULT_MULT = 1.6
DEFAULT_SOURCE = "hlc3"


def hlc3(high: float, low: float, close: float) -> float:
    return (high + low + close) / 3.0


def alpha_from_length(length: int) -> float:
    if length < 1:
        raise ValueError("length must be >= 1")
    return 2.0 / (length + 1.0)


def ema_series(values: list[float], alpha: float) -> list[float]:
    """Recursive EMA matching Pine `_ema` with nz(out[1], out) init.

    First bar: out = src (seed).
    Later bars: out = alpha * src + (1 - alpha) * previous_out
    """
    if not values:
        return []
    if not (0.0 < alpha <= 1.0):
        raise ValueError("alpha must be in (0, 1]")

    out: list[float] = [values[0]]
    for i in range(1, len(values)):
        out.append(alpha * values[i] + (1.0 - alpha) * out[i - 1])
    return out


def mnma_series(values: list[float], length: int) -> list[float]:
    """Modified normalized moving average from Pine `_mnma`."""
    alpha = alpha_from_length(length)
    ema1 = ema_series(values, alpha)
    ema2 = ema_series(ema1, alpha)
    denom = 1.0 - alpha
    if abs(denom) < 1e-15:
        raise ValueError("invalid alpha produces zero denominator")
    return [((2.0 - alpha) * e1 - e2) / denom for e1, e2 in zip(ema1, ema2)]


@dataclass(frozen=True, slots=True)
class VortexBandsRow:
    basis: float
    upper: float
    lower: float
    source: float


def source_series(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    source: str = DEFAULT_SOURCE,
) -> list[float]:
    source = source.lower()
    if source == "hlc3":
        return [hlc3(h, l, c) for h, l, c in zip(highs, lows, closes)]
    if source == "close":
        return list(closes)
    raise ValueError(f"Unsupported source: {source}")


def calculate_vortex_bands(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    *,
    length: int = DEFAULT_LENGTH,
    mult: float = DEFAULT_MULT,
    source: str = DEFAULT_SOURCE,
) -> list[VortexBandsRow]:
    """Compute Vortex Bands for each bar using only data up to that bar."""
    n = len(closes)
    if not (len(highs) == len(lows) == n):
        raise ValueError("highs, lows, closes must have equal length")
    if n == 0:
        return []

    src = source_series(highs, lows, closes, source)
    basis = mnma_series(src, length)
    deviation_input = [s - b for s, b in zip(src, basis)]
    dev = [mult * v for v in mnma_series(deviation_input, length)]

    return [
        VortexBandsRow(
            basis=basis[i],
            upper=basis[i] + dev[i],
            lower=basis[i] - dev[i],
            source=src[i],
        )
        for i in range(n)
    ]
