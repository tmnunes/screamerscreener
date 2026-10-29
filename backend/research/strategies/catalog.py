"""Deterministic strategy catalog across families A–F.

Design notes (after fee-aware diagnosis):
- 5m always-in-market trend systems are crippled by taker fees; keep a few as
  negative controls, emphasize 15m/1h and multi-timeframe filtered entries.
- Default risk exits use signal flips; ATR stops are reserved for breakouts.
"""

from __future__ import annotations

import pandas as pd

from backend.research.indicators import core as ind
from backend.research.strategies.base import StrategySpec


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "timestamp" not in out.columns:
        out["timestamp"] = pd.to_datetime(out["open_time"], unit="ms", utc=True)
    return out.reset_index(drop=True)


def _htf_trend_ema(htf: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.DataFrame:
    h = _prepare(htf)
    h["ema_fast"] = ind.ema(h["close"], fast)
    h["ema_slow"] = ind.ema(h["close"], slow)
    h["htf_trend"] = 0
    h.loc[h["ema_fast"] > h["ema_slow"], "htf_trend"] = 1
    h.loc[h["ema_fast"] < h["ema_slow"], "htf_trend"] = -1
    h["adx"] = ind.adx_di(h["high"], h["low"], h["close"], 14)[0]
    h["ema200"] = ind.ema(h["close"], 200)
    return h


def _attach_htf(ltf: pd.DataFrame, htf: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    aligned = ind.align_htf_to_ltf(ltf, htf, cols)
    out = ltf.copy()
    for c in cols:
        out[c] = aligned[c].values
    return out


def _cross_signal(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """Stay in direction of last cross (stateful), not raw level comparison churn."""
    above = (fast > slow).fillna(False).astype(bool)
    prev = above.shift(1).fillna(False).astype(bool)
    cross_up = above & ~prev
    cross_dn = (~above) & prev
    state = 0
    out = []
    for i in range(len(fast)):
        if cross_up.iloc[i]:
            state = 1
        elif cross_dn.iloc[i]:
            state = -1
        out.append(state)
    return pd.Series(out, index=fast.index)


# --- Family A: Trend ---

def sig_ema_cross(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    return _cross_signal(ind.ema(d["close"], 20), ind.ema(d["close"], 50))


def sig_ema_adx(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    base = _cross_signal(ind.ema(d["close"], 20), ind.ema(d["close"], 50))
    adx, _, _ = ind.adx_di(d["high"], d["low"], d["close"], 14)
    return base.where(adx >= 25, 0).fillna(0).astype(int)


def sig_ema_rsi(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    base = _cross_signal(ind.ema(d["close"], 20), ind.ema(d["close"], 50))
    r = ind.rsi(d["close"], 14)
    sig = pd.Series(0, index=d.index)
    sig[(base == 1) & (r >= 50)] = 1
    sig[(base == -1) & (r <= 50)] = -1
    return sig


def sig_ema_triple(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    e20 = ind.ema(d["close"], 20)
    e50 = ind.ema(d["close"], 50)
    e200 = ind.ema(d["close"], 200)
    sig = pd.Series(0, index=d.index)
    sig[(e20 > e50) & (e50 > e200)] = 1
    sig[(e20 < e50) & (e50 < e200)] = -1
    return sig


# --- Family B: Momentum ---

def sig_rsi_continuation(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    r = ind.rsi(d["close"], 14)
    # Enter only on threshold cross; exit on mid-line reclaim
    state = 0
    out = []
    for i in range(len(d)):
        ri = r.iloc[i]
        if ri != ri:
            out.append(state)
            continue
        if state == 0:
            if ri >= 60:
                state = 1
            elif ri <= 40:
                state = -1
        elif state == 1 and ri < 50:
            state = 0
        elif state == -1 and ri > 50:
            state = 0
        out.append(state)
    return pd.Series(out, index=d.index)


def sig_macd_cross(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    line, signal, _ = ind.macd(d["close"])
    return _cross_signal(line, signal)


def sig_rsi_macd(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    r = ind.rsi(d["close"], 14)
    macd_sig = sig_macd_cross(d)
    sig = pd.Series(0, index=d.index)
    sig[(macd_sig == 1) & (r >= 50)] = 1
    sig[(macd_sig == -1) & (r <= 50)] = -1
    return sig


# --- Family C: Breakout ---

def sig_donchian(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    upper, _, lower = ind.donchian(d["high"], d["low"], 55)
    prev_upper = upper.shift(1)
    prev_lower = lower.shift(1)
    mid = (prev_upper + prev_lower) / 2
    state = 0
    out = []
    for i in range(len(d)):
        c = d["close"].iloc[i]
        if prev_upper.iloc[i] == prev_upper.iloc[i] and c > prev_upper.iloc[i]:
            state = 1
        elif prev_lower.iloc[i] == prev_lower.iloc[i] and c < prev_lower.iloc[i]:
            state = -1
        elif state == 1 and c < mid.iloc[i]:
            state = 0
        elif state == -1 and c > mid.iloc[i]:
            state = 0
        out.append(state)
    return pd.Series(out, index=d.index)


def sig_bb_breakout(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    mid, upper, lower, width = ind.bollinger(d["close"], 20, 2.0)
    width_ma = width.rolling(100, min_periods=100).mean()
    squeeze = width < (width_ma * 0.85)
    state = 0
    out = []
    for i in range(len(d)):
        if i == 0:
            out.append(0)
            continue
        if squeeze.iloc[i - 1]:
            if d["close"].iloc[i] > upper.iloc[i - 1]:
                state = 1
            elif d["close"].iloc[i] < lower.iloc[i - 1]:
                state = -1
        if state == 1 and d["close"].iloc[i] < mid.iloc[i]:
            state = 0
        elif state == -1 and d["close"].iloc[i] > mid.iloc[i]:
            state = 0
        out.append(state)
    return pd.Series(out, index=d.index)


def sig_donchian_rvol(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    base = sig_donchian(d)
    rvol = ind.relative_volume(d["volume"], 20)
    # Keep position once entered; only block fresh entries without volume
    state = 0
    out = []
    for i in range(len(d)):
        b = int(base.iloc[i])
        if state == 0 and b != 0 and rvol.iloc[i] == rvol.iloc[i] and rvol.iloc[i] >= 1.3:
            state = b
        elif state != 0 and b == 0:
            state = 0
        elif state != 0 and b == -state:
            state = b if (rvol.iloc[i] == rvol.iloc[i] and rvol.iloc[i] >= 1.3) else 0
        out.append(state)
    return pd.Series(out, index=d.index)


# --- Family D: Mean reversion ---

def sig_bb_rsi_mr(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    mid, upper, lower, _ = ind.bollinger(d["close"], 20, 2.0)
    r = ind.rsi(d["close"], 14)
    adx, _, _ = ind.adx_di(d["high"], d["low"], d["close"], 14)
    low_trend = adx < 18
    state = 0
    out = []
    for i in range(len(d)):
        if low_trend.iloc[i]:
            if d["close"].iloc[i] < lower.iloc[i] and r.iloc[i] is not None and r.iloc[i] < 30:
                state = 1
            elif d["close"].iloc[i] > upper.iloc[i] and r.iloc[i] is not None and r.iloc[i] > 70:
                state = -1
            elif state == 1 and d["close"].iloc[i] >= mid.iloc[i]:
                state = 0
            elif state == -1 and d["close"].iloc[i] <= mid.iloc[i]:
                state = 0
        else:
            state = 0
        out.append(state)
    return pd.Series(out, index=d.index)


def sig_zscore_mr(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    z = ind.rolling_zscore(d["close"], 48)
    adx, _, _ = ind.adx_di(d["high"], d["low"], d["close"], 14)
    low_trend = adx < 18
    state = 0
    out = []
    for i in range(len(d)):
        zi = z.iloc[i]
        if low_trend.iloc[i] and zi == zi:
            if zi <= -2.5:
                state = 1
            elif zi >= 2.5:
                state = -1
            elif state == 1 and zi >= 0:
                state = 0
            elif state == -1 and zi <= 0:
                state = 0
        else:
            state = 0
        out.append(state)
    return pd.Series(out, index=d.index)


# --- Family E: Multi-timeframe ---

def sig_htf_ema_ltf_rsi(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    if htf is None:
        return pd.Series(0, index=df.index)
    d = _prepare(df)
    h = _htf_trend_ema(htf)
    d = _attach_htf(d, h, ["htf_trend", "adx"])
    r = ind.rsi(d["close"], 14)
    state = 0
    out = []
    for i in range(len(d)):
        trend = d["htf_trend"].iloc[i]
        adx = d["adx"].iloc[i]
        ri = r.iloc[i]
        if trend != trend or adx != adx or ri != ri:
            out.append(state)
            continue
        if state == 0 and adx >= 20:
            if trend == 1 and ri >= 58:
                state = 1
            elif trend == -1 and ri <= 42:
                state = -1
        elif state == 1 and (trend != 1 or ri < 48):
            state = 0
        elif state == -1 and (trend != -1 or ri > 52):
            state = 0
        out.append(state)
    return pd.Series(out, index=d.index)


def sig_htf_adx_ltf_mom(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    if htf is None:
        return pd.Series(0, index=df.index)
    d = _prepare(df)
    h = _htf_trend_ema(htf)
    d = _attach_htf(d, h, ["htf_trend", "adx"])
    macd_sig = sig_macd_cross(d)
    sig = pd.Series(0, index=d.index)
    strong = d["adx"] >= 25
    sig[strong & (d["htf_trend"] == 1) & (macd_sig == 1)] = 1
    sig[strong & (d["htf_trend"] == -1) & (macd_sig == -1)] = -1
    return sig


def sig_htf_trend_ltf_breakout(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    if htf is None:
        return pd.Series(0, index=df.index)
    d = _prepare(df)
    h = _htf_trend_ema(htf)
    d = _attach_htf(d, h, ["htf_trend"])
    base = sig_donchian(d)
    sig = base.where(
        ((base == 1) & (d["htf_trend"] == 1)) | ((base == -1) & (d["htf_trend"] == -1)) | (base == 0),
        0,
    )
    return sig.fillna(0).astype(int)


# --- Family F: Hybrid ---

def sig_trend_mom_atr(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    base = _cross_signal(ind.ema(d["close"], 20), ind.ema(d["close"], 50))
    r = ind.rsi(d["close"], 14)
    adx, _, _ = ind.adx_di(d["high"], d["low"], d["close"], 14)
    sig = pd.Series(0, index=d.index)
    sig[(base == 1) & (r >= 52) & (adx >= 20)] = 1
    sig[(base == -1) & (r <= 48) & (adx >= 20)] = -1
    return sig


def sig_squeeze_break_htf(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    d = _prepare(df)
    base = sig_bb_breakout(d)
    if htf is None:
        return base
    h = _htf_trend_ema(htf)
    d = _attach_htf(d, h, ["htf_trend"])
    sig = base.where(
        (base == 0)
        | ((base == 1) & (d["htf_trend"] == 1))
        | ((base == -1) & (d["htf_trend"] == -1)),
        0,
    )
    return sig.fillna(0).astype(int)


def sig_mr_low_adx(df: pd.DataFrame, htf: pd.DataFrame | None = None) -> pd.Series:
    return sig_bb_rsi_mr(df, htf)


def build_catalog() -> list[StrategySpec]:
    # stop_atr_mult=None → signal exits only (avoids stop-induced fee churn)
    # Winning optimize hits are registered at the top for easy re-runs.
    from backend.research.optimize import sig_ema_adx_params, sig_keltner_break

    def _ema_adx_win(df, htf=None):
        return sig_ema_adx_params(df, htf, {"fast": 12, "slow": 50, "adx_thr": 30})

    def _kelt_win(df, htf=None):
        return sig_keltner_break(df, htf, {"len": 20, "mult": 2.5})

    return [
        StrategySpec(
            "WIN_EMAADX_12_50_a30_1h",
            "trend",
            "Optimize winner: EMA12/50 ADX30 ATR stop/TP",
            "1h",
            None,
            _ema_adx_win,
            2.5,
            4.0,
        ),
        StrategySpec(
            "WIN_KELT_20x2.5_1h",
            "breakout",
            "Optimize winner: Keltner 20x2.5",
            "1h",
            None,
            _kelt_win,
            2.5,
            5.0,
        ),

        # Negative-control / high-turnover references on 5m
        StrategySpec("A1_ema20_50_5m", "trend", "EMA 20/50 cross 5m", "5m", None, sig_ema_cross, None, None),
        StrategySpec("A2_ema_adx_5m", "trend", "EMA+ADX 5m", "5m", None, sig_ema_adx, None, None),
        # Core 15m / 1h research set
        StrategySpec("A1_ema20_50_15m", "trend", "EMA 20/50 cross 15m", "15m", None, sig_ema_cross, None, None),
        StrategySpec("A2_ema_adx_15m", "trend", "EMA+ADX>=25 15m", "15m", None, sig_ema_adx, None, None),
        StrategySpec("A3_ema_rsi_15m", "trend", "EMA+RSI 15m", "15m", None, sig_ema_rsi, None, None),
        StrategySpec("A4_ema_triple_15m", "trend", "EMA 20/50/200 15m", "15m", None, sig_ema_triple, None, None),
        StrategySpec("A1_ema20_50_1h", "trend", "EMA 20/50 cross 1h", "1h", None, sig_ema_cross, None, None),
        StrategySpec("A2_ema_adx_1h", "trend", "EMA+ADX 1h", "1h", None, sig_ema_adx, None, None),
        StrategySpec("A4_ema_triple_1h", "trend", "EMA triple 1h", "1h", None, sig_ema_triple, None, None),
        StrategySpec("B1_rsi_cont_15m", "momentum", "RSI continuation 15m", "15m", None, sig_rsi_continuation, None, None),
        StrategySpec("B2_macd_15m", "momentum", "MACD cross 15m", "15m", None, sig_macd_cross, None, None),
        StrategySpec("B3_rsi_macd_15m", "momentum", "RSI+MACD 15m", "15m", None, sig_rsi_macd, None, None),
        StrategySpec("B2_macd_1h", "momentum", "MACD cross 1h", "1h", None, sig_macd_cross, None, None),
        StrategySpec("C1_donchian55_15m", "breakout", "Donchian 55 15m", "15m", None, sig_donchian, 3.0, None),
        StrategySpec("C1_donchian55_1h", "breakout", "Donchian 55 1h", "1h", None, sig_donchian, 3.0, None),
        StrategySpec("C2_bb_squeeze_15m", "breakout", "BB squeeze 15m", "15m", None, sig_bb_breakout, 2.5, None),
        StrategySpec("C3_don_rvol_1h", "breakout", "Donchian+RVOL 1h", "1h", None, sig_donchian_rvol, 3.0, None),
        StrategySpec("D1_bb_rsi_mr_15m", "mean_reversion", "BB+RSI MR 15m", "15m", None, sig_bb_rsi_mr, 1.8, None, 64),
        StrategySpec("D2_zscore_mr_15m", "mean_reversion", "Z-score MR 15m", "15m", None, sig_zscore_mr, 1.8, None, 64),
        StrategySpec("D1_bb_rsi_mr_1h", "mean_reversion", "BB+RSI MR 1h", "1h", None, sig_bb_rsi_mr, 1.8, None, 48),
        StrategySpec("E1_1h_ema_15m_rsi", "multi_tf", "1h trend + 15m RSI", "15m", "1h", sig_htf_ema_ltf_rsi, None, None),
        StrategySpec("E2_1h_adx_15m_macd", "multi_tf", "1h ADX + 15m MACD", "15m", "1h", sig_htf_adx_ltf_mom, None, None),
        StrategySpec("E3_1h_trend_15m_don", "multi_tf", "1h trend + 15m Donchian", "15m", "1h", sig_htf_trend_ltf_breakout, 3.0, None),
        StrategySpec("E1_1h_ema_5m_rsi", "multi_tf", "1h trend + 5m RSI", "5m", "1h", sig_htf_ema_ltf_rsi, None, None),
        StrategySpec("F1_trend_mom_15m", "hybrid", "Trend+mom+ADX 15m", "15m", None, sig_trend_mom_atr, None, None),
        StrategySpec("F1_trend_mom_1h", "hybrid", "Trend+mom+ADX 1h", "1h", None, sig_trend_mom_atr, None, None),
        StrategySpec("F2_squeeze_htf_15m", "hybrid", "Squeeze+1h trend 15m", "15m", "1h", sig_squeeze_break_htf, 2.5, None),
        StrategySpec("F3_mr_low_adx_15m", "hybrid", "MR low-ADX 15m", "15m", None, sig_mr_low_adx, 1.8, None, 64),
    ]
