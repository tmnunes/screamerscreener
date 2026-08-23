"""Reusable moving-average / series helpers for secondary indicators."""

from __future__ import annotations

from backend.indicators.vortex_bands import alpha_from_length, ema_series


def sma_series(values: list[float], length: int) -> list[float | None]:
    """Simple moving average. None until enough bars exist."""
    if length < 1:
        raise ValueError("length must be >= 1")
    out: list[float | None] = []
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= length:
            running -= values[i - length]
        if i + 1 < length:
            out.append(None)
        else:
            out.append(running / length)
    return out


def ema_length_series(values: list[float], length: int) -> list[float]:
    """EMA seeded like Pine recursive EMA (first bar = src)."""
    return ema_series(values, alpha_from_length(length))


def true_range_series(
    highs: list[float], lows: list[float], closes: list[float]
) -> list[float]:
    out: list[float] = []
    for i in range(len(closes)):
        if i == 0:
            out.append(highs[i] - lows[i])
        else:
            out.append(
                max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]),
                )
            )
    return out


def rma_series(values: list[float], length: int) -> list[float | None]:
    """Wilder RMA. None until seed (SMA of first `length` bars)."""
    if length < 1:
        raise ValueError("length must be >= 1")
    out: list[float | None] = [None] * len(values)
    if len(values) < length:
        return out
    alpha = 1.0 / length
    seed = sum(values[:length]) / length
    out[length - 1] = seed
    for i in range(length, len(values)):
        prev = out[i - 1]
        assert prev is not None
        out[i] = alpha * values[i] + (1.0 - alpha) * prev
    return out


def rolling_max(values: list[float], length: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < length:
            out.append(None)
        else:
            out.append(max(values[i + 1 - length : i + 1]))
    return out


def rolling_min(values: list[float], length: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < length:
            out.append(None)
        else:
            out.append(min(values[i + 1 - length : i + 1]))
    return out


def rsi_series(closes: list[float], length: int = 14) -> list[float | None]:
    """Wilder RSI. None until enough bars exist."""
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
    for g, loss in zip(avg_gain, avg_loss):
        if g is None or loss is None:
            out.append(None)
        elif loss == 0:
            out.append(100.0)
        else:
            rs = g / loss
            out.append(100.0 - (100.0 / (1.0 + rs)))
    return out
