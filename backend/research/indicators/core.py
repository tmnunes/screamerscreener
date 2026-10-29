"""Causal indicator calculations (no look-ahead).

All outputs at index i use only data at indices <= i.
Higher-timeframe joins must use completed HTF bars only (see align_htf).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    ranges = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    out = out.where(avg_loss != 0, 100.0)
    return out


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    hist = line - sig
    return line, sig, hist


def stochastic_rsi(
    close: pd.Series,
    rsi_len: int = 14,
    stoch_len: int = 14,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> tuple[pd.Series, pd.Series]:
    r = rsi(close, rsi_len)
    lowest = r.rolling(stoch_len, min_periods=stoch_len).min()
    highest = r.rolling(stoch_len, min_periods=stoch_len).max()
    stoch = (r - lowest) / (highest - lowest).replace(0, np.nan)
    k = stoch.rolling(k_smooth, min_periods=k_smooth).mean() * 100
    d = k.rolling(d_smooth, min_periods=d_smooth).mean()
    return k, d


def roc(close: pd.Series, length: int = 14) -> pd.Series:
    return close.pct_change(length) * 100


def momentum(close: pd.Series, length: int = 10) -> pd.Series:
    return close - close.shift(length)


def bollinger(
    close: pd.Series, length: int = 20, mult: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    mid = sma(close, length)
    std = close.rolling(length, min_periods=length).std()
    upper = mid + mult * std
    lower = mid - mult * std
    width = (upper - lower) / mid
    return mid, upper, lower, width


def keltner(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 20,
    atr_len: int = 10,
    mult: float = 1.5,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = ema(close, length)
    band = atr(high, low, close, atr_len) * mult
    return mid, mid + band, mid - band


def donchian(
    high: pd.Series, low: pd.Series, length: int = 20
) -> tuple[pd.Series, pd.Series, pd.Series]:
    upper = high.rolling(length, min_periods=length).max()
    lower = low.rolling(length, min_periods=length).min()
    mid = (upper + lower) / 2
    return upper, mid, lower


def adx_di(
    high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series]:
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(high, low, close)
    atr_ = tr.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    plus_di = (
        100
        * pd.Series(plus_dm, index=high.index)
        .ewm(alpha=1 / length, adjust=False, min_periods=length)
        .mean()
        / atr_
    )
    minus_di = (
        100
        * pd.Series(minus_dm, index=high.index)
        .ewm(alpha=1 / length, adjust=False, min_periods=length)
        .mean()
        / atr_
    )
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    return adx, plus_di, minus_di


def supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 10,
    mult: float = 3.0,
) -> tuple[pd.Series, pd.Series]:
    atr_ = atr(high, low, close, length)
    hl2 = (high + low) / 2
    basic_ub = hl2 + mult * atr_
    basic_lb = hl2 - mult * atr_
    final_ub = basic_ub.copy()
    final_lb = basic_lb.copy()
    for i in range(1, len(close)):
        final_ub.iloc[i] = (
            basic_ub.iloc[i]
            if basic_ub.iloc[i] < final_ub.iloc[i - 1] or close.iloc[i - 1] > final_ub.iloc[i - 1]
            else final_ub.iloc[i - 1]
        )
        final_lb.iloc[i] = (
            basic_lb.iloc[i]
            if basic_lb.iloc[i] > final_lb.iloc[i - 1] or close.iloc[i - 1] < final_lb.iloc[i - 1]
            else final_lb.iloc[i - 1]
        )
    direction = pd.Series(1, index=close.index, dtype=float)
    st = final_lb.copy()
    for i in range(1, len(close)):
        if close.iloc[i] > final_ub.iloc[i - 1]:
            direction.iloc[i] = 1
        elif close.iloc[i] < final_lb.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
        st.iloc[i] = final_lb.iloc[i] if direction.iloc[i] == 1 else final_ub.iloc[i]
    return st, direction


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def relative_volume(volume: pd.Series, length: int = 20) -> pd.Series:
    avg = volume.rolling(length, min_periods=length).mean()
    return volume / avg.replace(0, np.nan)


def rolling_zscore(close: pd.Series, length: int = 20) -> pd.Series:
    mu = close.rolling(length, min_periods=length).mean()
    sd = close.rolling(length, min_periods=length).std()
    return (close - mu) / sd.replace(0, np.nan)


def candle_features(df: pd.DataFrame) -> pd.DataFrame:
    body = (df["close"] - df["open"]).abs()
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
    lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
    out = pd.DataFrame(index=df.index)
    out["body_ratio"] = body / rng
    out["upper_wick_ratio"] = upper_wick / rng
    out["lower_wick_ratio"] = lower_wick / rng
    out["hh"] = (df["high"] > df["high"].shift(1)).astype(int)
    out["hl"] = (df["low"] > df["low"].shift(1)).astype(int)
    out["lh"] = (df["high"] < df["high"].shift(1)).astype(int)
    out["ll"] = (df["low"] < df["low"].shift(1)).astype(int)
    return out


def align_htf_to_ltf(
    ltf: pd.DataFrame,
    htf: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """Map completed HTF values onto LTF bars without look-ahead.

    Uses merge_asof with direction='backward' on HTF *close* timestamps so a
    5m bar only sees HTF candles that have already closed.
    """
    left = ltf[["timestamp"]].copy()
    right = htf[["timestamp"] + columns].copy()
    left["timestamp"] = pd.to_datetime(left["timestamp"], utc=True).astype(
        "datetime64[ns, UTC]"
    )
    right["timestamp"] = pd.to_datetime(right["timestamp"], utc=True).astype(
        "datetime64[ns, UTC]"
    )
    # HTF decision time = candle close. Bars are left-labeled.
    if len(htf) >= 2:
        step = right["timestamp"].iloc[1] - right["timestamp"].iloc[0]
    else:
        step = pd.Timedelta(hours=1)
    right = right.rename(columns={"timestamp": "htf_open"})
    right["timestamp"] = right["htf_open"] + step - pd.Timedelta(milliseconds=1)
    merged = pd.merge_asof(
        left.sort_values("timestamp"),
        right.sort_values("timestamp"),
        on="timestamp",
        direction="backward",
    )
    return merged[columns]
