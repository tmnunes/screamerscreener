"""Aggressive parameter / rule search for net-positive perpetual strategies."""

from __future__ import annotations

import itertools
import logging
import uuid
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from backend.research.backtest.engine import run_backtest
from backend.research.config import CostModel, REPORTS_DIR
from backend.research import db as research_db
from backend.research.indicators import core as ind
from backend.research.ranking import composite_score, walk_forward_split

logger = logging.getLogger(__name__)

SignalBuilder = Callable[[pd.DataFrame, pd.DataFrame | None, dict], pd.Series]


@dataclass(slots=True)
class TrialSpec:
    strategy_id: str
    family: str
    timeframe: str
    htf: str | None
    params: dict
    build: SignalBuilder
    stop_atr_mult: float | None = None
    take_atr_mult: float | None = None
    max_hold_bars: int | None = None


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().reset_index(drop=True)
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    return out


def _attach_htf(ltf: pd.DataFrame, htf: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    aligned = ind.align_htf_to_ltf(ltf, htf, cols)
    out = ltf.copy()
    for c in cols:
        out[c] = aligned[c].values
    return out


def sig_ema_cross_params(df: pd.DataFrame, htf: pd.DataFrame | None, p: dict) -> pd.Series:
    d = _prep(df)
    fast = ind.ema(d["close"], int(p["fast"]))
    slow = ind.ema(d["close"], int(p["slow"]))
    above = (fast > slow).fillna(False).astype(bool)
    prev = above.shift(1).fillna(False).astype(bool)
    state = 0
    out = []
    for i in range(len(d)):
        if bool(above.iloc[i] and not prev.iloc[i]):
            state = 1
        elif bool((not above.iloc[i]) and prev.iloc[i]):
            state = -1
        if p.get("long_only"):
            state = 1 if state == 1 else 0
        if p.get("short_only"):
            state = -1 if state == -1 else 0
        out.append(state)
    return pd.Series(out, index=d.index)


def sig_ema_adx_params(df: pd.DataFrame, htf: pd.DataFrame | None, p: dict) -> pd.Series:
    base = sig_ema_cross_params(df, htf, p)
    d = _prep(df)
    adx, _, _ = ind.adx_di(d["high"], d["low"], d["close"], int(p.get("adx_len", 14)))
    thr = float(p.get("adx_thr", 25))
    return base.where(adx >= thr, 0).fillna(0).astype(int)


def sig_triple_params(df: pd.DataFrame, htf: pd.DataFrame | None, p: dict) -> pd.Series:
    d = _prep(df)
    e1 = ind.ema(d["close"], int(p["fast"]))
    e2 = ind.ema(d["close"], int(p["mid"]))
    e3 = ind.ema(d["close"], int(p["slow"]))
    sig = pd.Series(0, index=d.index)
    sig[(e1 > e2) & (e2 > e3)] = 1
    sig[(e1 < e2) & (e2 < e3)] = -1
    if p.get("long_only"):
        sig = sig.where(sig == 1, 0)
    return sig.astype(int)


def sig_pullback_trend(df: pd.DataFrame, htf: pd.DataFrame | None, p: dict) -> pd.Series:
    """HTF trend + LTF pullback to EMA then resume."""
    d = _prep(df)
    if htf is None:
        return pd.Series(0, index=d.index)
    h = _prep(htf)
    h["ema_slow"] = ind.ema(h["close"], int(p.get("htf_ema", 100)))
    h["htf_trend"] = np.where(h["close"] > h["ema_slow"], 1, -1)
    d = _attach_htf(d, h, ["htf_trend"])
    ema_pb = ind.ema(d["close"], int(p.get("pb_ema", 20)))
    rsi = ind.rsi(d["close"], int(p.get("rsi_len", 14)))
    state = 0
    out = []
    touched = False
    for i in range(len(d)):
        trend = d["htf_trend"].iloc[i]
        if trend != trend or rsi.iloc[i] != rsi.iloc[i]:
            out.append(state)
            continue
        # require pullback touch then reclaim
        if state == 0:
            if trend == 1 and d["low"].iloc[i] <= ema_pb.iloc[i]:
                touched = True
            if trend == -1 and d["high"].iloc[i] >= ema_pb.iloc[i]:
                touched = True
            if touched and trend == 1 and d["close"].iloc[i] > ema_pb.iloc[i] and rsi.iloc[i] >= p.get("rsi_on", 50):
                state = 1
                touched = False
            elif touched and trend == -1 and d["close"].iloc[i] < ema_pb.iloc[i] and rsi.iloc[i] <= (100 - p.get("rsi_on", 50)):
                state = -1
                touched = False
        elif state == 1 and (trend != 1 or d["close"].iloc[i] < ema_pb.iloc[i] * (1 - p.get("exit_buf", 0.0))):
            state = 0
            touched = False
        elif state == -1 and (trend != -1 or d["close"].iloc[i] > ema_pb.iloc[i] * (1 + p.get("exit_buf", 0.0))):
            state = 0
            touched = False
        if p.get("long_only") and state == -1:
            state = 0
        if p.get("short_only") and state == 1:
            state = 0
        out.append(state)
    return pd.Series(out, index=d.index)


def sig_mr_params(df: pd.DataFrame, htf: pd.DataFrame | None, p: dict) -> pd.Series:
    d = _prep(df)
    mid, upper, lower, _ = ind.bollinger(d["close"], int(p["bb_len"]), float(p["bb_mult"]))
    rsi = ind.rsi(d["close"], int(p.get("rsi_len", 14)))
    adx, _, _ = ind.adx_di(d["high"], d["low"], d["close"], int(p.get("adx_len", 14)))
    # early TP level between band and mid
    long_tp = mid - (mid - lower) * float(p.get("tp_frac", 0.0))
    short_tp = mid + (upper - mid) * float(p.get("tp_frac", 0.0))
    if float(p.get("tp_frac", 0.0)) <= 0:
        long_tp = mid
        short_tp = mid
    state = 0
    out = []
    for i in range(len(d)):
        if adx.iloc[i] != adx.iloc[i] or rsi.iloc[i] != rsi.iloc[i]:
            out.append(state)
            continue
        if adx.iloc[i] < float(p["adx_max"]):
            if state == 0:
                if d["close"].iloc[i] < lower.iloc[i] and rsi.iloc[i] <= float(p["rsi_buy"]):
                    state = 1
                elif d["close"].iloc[i] > upper.iloc[i] and rsi.iloc[i] >= float(p["rsi_sell"]):
                    state = -1
            elif state == 1 and d["close"].iloc[i] >= long_tp.iloc[i]:
                state = 0
            elif state == -1 and d["close"].iloc[i] <= short_tp.iloc[i]:
                state = 0
        else:
            state = 0
        out.append(state)
    return pd.Series(out, index=d.index)


def sig_donchian_params(df: pd.DataFrame, htf: pd.DataFrame | None, p: dict) -> pd.Series:
    d = _prep(df)
    entry_n = int(p["entry"])
    exit_n = int(p["exit"])
    up_e, _, lo_e = ind.donchian(d["high"], d["low"], entry_n)
    up_x, _, lo_x = ind.donchian(d["high"], d["low"], exit_n)
    state = 0
    out = []
    for i in range(len(d)):
        if i == 0:
            out.append(0)
            continue
        c = d["close"].iloc[i]
        if state == 0:
            if up_e.shift(1).iloc[i] == up_e.shift(1).iloc[i] and c > up_e.shift(1).iloc[i]:
                state = 1
            elif lo_e.shift(1).iloc[i] == lo_e.shift(1).iloc[i] and c < lo_e.shift(1).iloc[i]:
                state = -1
        elif state == 1 and c < lo_x.shift(1).iloc[i]:
            state = 0
        elif state == -1 and c > up_x.shift(1).iloc[i]:
            state = 0
        if p.get("long_only") and state < 0:
            state = 0
        out.append(state)
    return pd.Series(out, index=d.index)


def sig_supertrend_params(df: pd.DataFrame, htf: pd.DataFrame | None, p: dict) -> pd.Series:
    d = _prep(df)
    _, direction = ind.supertrend(
        d["high"], d["low"], d["close"], int(p.get("atr_len", 10)), float(p.get("mult", 3.0))
    )
    sig = direction.fillna(0).astype(int)
    if p.get("long_only"):
        sig = sig.where(sig == 1, 0)
    return sig


def sig_funding_fade(df: pd.DataFrame, htf: pd.DataFrame | None, p: dict) -> pd.Series:
    """Fade extreme funding using funding series attached as htf-like frame with rate col.

    Expects ``htf`` to actually be a funding DataFrame with timestamp + funding_rate,
    pre-aligned by caller via params['_funding'].
    """
    d = _prep(df)
    funding: pd.DataFrame | None = p.get("_funding")
    if funding is None or funding.empty:
        return pd.Series(0, index=d.index)
    f = funding.sort_values("timestamp").copy()
    f["timestamp"] = pd.to_datetime(f["timestamp"], utc=True)
    merged = pd.merge_asof(
        d[["timestamp"]].assign(
            timestamp=lambda x: pd.to_datetime(x["timestamp"], utc=True).astype(
                "datetime64[ns, UTC]"
            )
        ),
        f[["timestamp", "funding_rate"]].assign(
            timestamp=lambda x: pd.to_datetime(x["timestamp"], utc=True).astype(
                "datetime64[ns, UTC]"
            )
        ),
        on="timestamp",
        direction="backward",
    )
    rate = merged["funding_rate"]
    hi = float(p.get("fund_hi", 0.0005))
    lo = float(p.get("fund_lo", -0.0003))
    hold = int(p.get("hold", 24))
    state = 0
    left = 0
    out = []
    for i in range(len(d)):
        r = rate.iloc[i]
        if state != 0:
            left -= 1
            if left <= 0:
                state = 0
        if state == 0 and r == r:
            if r >= hi:
                state = -1
                left = hold
            elif r <= lo:
                state = 1
                left = hold
        out.append(state)
    return pd.Series(out, index=d.index)


def sig_keltner_break(df: pd.DataFrame, htf: pd.DataFrame | None, p: dict) -> pd.Series:
    d = _prep(df)
    mid, up, lo = ind.keltner(
        d["high"], d["low"], d["close"], int(p.get("len", 20)), int(p.get("atr_len", 10)), float(p.get("mult", 1.5))
    )
    state = 0
    out = []
    for i in range(len(d)):
        if i == 0:
            out.append(0)
            continue
        if state == 0:
            if d["close"].iloc[i] > up.shift(1).iloc[i]:
                state = 1
            elif d["close"].iloc[i] < lo.shift(1).iloc[i]:
                state = -1
        elif state == 1 and d["close"].iloc[i] < mid.iloc[i]:
            state = 0
        elif state == -1 and d["close"].iloc[i] > mid.iloc[i]:
            state = 0
        out.append(state)
    return pd.Series(out, index=d.index)


def build_search_space() -> list[TrialSpec]:
    """Dense but tractable grid (~250 trials) across families + risk params."""
    trials: list[TrialSpec] = []

    # EMA crosses — focus 1h + selective 15m, long-only variants
    for tf, fast, slow, long_only in itertools.product(
        ("1h", "15m"),
        (12, 20, 50),
        (50, 100, 200),
        (False, True),
    ):
        if fast >= slow:
            continue
        if tf == "15m" and slow == 200 and fast != 20:
            continue
        trials.append(
            TrialSpec(
                f"EMA_{fast}_{slow}_{tf}{'_L' if long_only else ''}",
                "trend",
                tf,
                None,
                {"fast": fast, "slow": slow, "long_only": long_only},
                sig_ema_cross_params,
                stop_atr_mult=2.5 if tf == "1h" else None,
                take_atr_mult=5.0 if tf == "1h" else None,
            )
        )

    # EMA + ADX (1h primary)
    for fast, slow, adx_thr, stop, take in itertools.product(
        (12, 20), (50, 100), (20, 25, 30), (None, 2.5), (None, 4.0)
    ):
        if stop is None and take is not None:
            continue
        trials.append(
            TrialSpec(
                f"EMAADX_{fast}_{slow}_a{adx_thr}_s{stop}_t{take}_1h",
                "trend",
                "1h",
                None,
                {"fast": fast, "slow": slow, "adx_thr": adx_thr},
                sig_ema_adx_params,
                stop_atr_mult=stop,
                take_atr_mult=take,
            )
        )

    for tf, long_only in itertools.product(("1h", "15m"), (False, True)):
        trials.append(
            TrialSpec(
                f"TRIPLE_20_50_200_{tf}{'_L' if long_only else ''}",
                "trend",
                tf,
                None,
                {"fast": 20, "mid": 50, "slow": 200, "long_only": long_only},
                sig_triple_params,
                stop_atr_mult=3.0,
                take_atr_mult=6.0,
            )
        )

    # Pullback with 1h HTF on 15m
    for htf_ema, pb_ema, rsi_on, long_only in itertools.product(
        (50, 100, 200), (10, 20), (50, 55), (False, True)
    ):
        trials.append(
            TrialSpec(
                f"PB_h{htf_ema}_e{pb_ema}_r{rsi_on}_15m{'_L' if long_only else ''}",
                "multi_tf",
                "15m",
                "1h",
                {
                    "htf_ema": htf_ema,
                    "pb_ema": pb_ema,
                    "rsi_on": rsi_on,
                    "long_only": long_only,
                },
                sig_pullback_trend,
                stop_atr_mult=2.5,
                take_atr_mult=4.0,
            )
        )

    # Mean reversion — curated grid + stops/TP
    for tf, bb_len, bb_mult, adx_max, rsi_buy, tp_frac, stop in itertools.product(
        ("15m", "1h"),
        (20, 30),
        (2.0, 2.5),
        (15, 20),
        (25, 30),
        (0.0, 0.5),
        (1.5, None),
    ):
        trials.append(
            TrialSpec(
                f"MR_bb{bb_len}x{bb_mult}_a{adx_max}_r{rsi_buy}_tp{tp_frac}_s{stop}_{tf}",
                "mean_reversion",
                tf,
                None,
                {
                    "bb_len": bb_len,
                    "bb_mult": bb_mult,
                    "adx_max": adx_max,
                    "rsi_buy": rsi_buy,
                    "rsi_sell": 100 - rsi_buy,
                    "tp_frac": tp_frac,
                },
                sig_mr_params,
                stop_atr_mult=stop,
                take_atr_mult=2.0 if tp_frac == 0 else None,
                max_hold_bars={"15m": 48, "30m": 36, "1h": 24}.get(tf),
            )
        )

    # Donchian turtle-style
    for tf, entry, exit_n, long_only in itertools.product(
        ("1h",), (55, 100), (10, 20, 50), (False, True)
    ):
        if exit_n >= entry:
            continue
        trials.append(
            TrialSpec(
                f"DON_{entry}_{exit_n}_{tf}{'_L' if long_only else ''}",
                "breakout",
                tf,
                None,
                {"entry": entry, "exit": exit_n, "long_only": long_only},
                sig_donchian_params,
                stop_atr_mult=3.0,
                take_atr_mult=6.0,
            )
        )

    # Supertrend 1h only (15m loop is too slow)
    for atr_len, mult, long_only in itertools.product(
        (10, 14), (2.5, 3.0, 4.0), (False, True)
    ):
        trials.append(
            TrialSpec(
                f"ST_{atr_len}x{mult}_1h{'_L' if long_only else ''}",
                "trend",
                "1h",
                None,
                {"atr_len": atr_len, "mult": mult, "long_only": long_only},
                sig_supertrend_params,
            )
        )

    for length, mult in itertools.product((20, 30), (1.5, 2.0, 2.5)):
        trials.append(
            TrialSpec(
                f"KELT_{length}x{mult}_1h",
                "breakout",
                "1h",
                None,
                {"len": length, "mult": mult},
                sig_keltner_break,
                stop_atr_mult=2.5,
                take_atr_mult=5.0,
            )
        )

    for fund_hi, fund_lo, hold in itertools.product(
        (0.0003, 0.0005, 0.0008), (-0.0002, -0.0004), (12, 24, 48)
    ):
        trials.append(
            TrialSpec(
                f"FUND_h{fund_hi}_l{fund_lo}_hold{hold}_1h",
                "hybrid",
                "1h",
                None,
                {"fund_hi": fund_hi, "fund_lo": fund_lo, "hold": hold},
                sig_funding_fade,
                max_hold_bars=hold,
            )
        )

    logger.info("Search space size: %s trials", len(trials))
    return trials


def build_freq_search_space() -> list[TrialSpec]:
    """Search biased to trade often enough (~≥1 trade / 1–2 weeks over 2y).

    Includes 5m / 15m / 1h. Excludes ultra-sparse funding fades.
    """
    trials: list[TrialSpec] = []

    # 5m: selective trend (ADX + ATR) — prior default grid skipped 5m
    for fast, slow, adx_thr, stop, take in itertools.product(
        (12, 20),
        (50, 100),
        (25, 30),
        (2.5, 3.0),
        (4.0, 5.0),
    ):
        trials.append(
            TrialSpec(
                f"EMAADX_{fast}_{slow}_a{adx_thr}_s{stop}_t{take}_5m",
                "trend",
                "5m",
                None,
                {"fast": fast, "slow": slow, "adx_thr": adx_thr},
                sig_ema_adx_params,
                stop_atr_mult=stop,
                take_atr_mult=take,
            )
        )

    # 5m pullback with 1h filter
    for htf_ema, pb_ema, rsi_on, long_only in itertools.product(
        (100, 200), (20,), (50, 55), (False, True)
    ):
        trials.append(
            TrialSpec(
                f"PB_h{htf_ema}_e{pb_ema}_r{rsi_on}_5m{'_L' if long_only else ''}",
                "multi_tf",
                "5m",
                "1h",
                {
                    "htf_ema": htf_ema,
                    "pb_ema": pb_ema,
                    "rsi_on": rsi_on,
                    "long_only": long_only,
                },
                sig_pullback_trend,
                stop_atr_mult=2.5,
                take_atr_mult=4.0,
            )
        )

    # 5m / 15m mean-reversion (more trades than funding)
    for tf, bb_len, bb_mult, adx_max, rsi_buy, stop in itertools.product(
        ("5m", "15m"),
        (20, 30),
        (2.0, 2.5),
        (18, 22),
        (30,),
        (1.5, 2.0),
    ):
        trials.append(
            TrialSpec(
                f"MR_bb{bb_len}x{bb_mult}_a{adx_max}_r{rsi_buy}_s{stop}_{tf}",
                "mean_reversion",
                tf,
                None,
                {
                    "bb_len": bb_len,
                    "bb_mult": bb_mult,
                    "adx_max": adx_max,
                    "rsi_buy": rsi_buy,
                    "rsi_sell": 100 - rsi_buy,
                    "tp_frac": 0.35,
                },
                sig_mr_params,
                stop_atr_mult=stop,
                take_atr_mult=2.5,
                max_hold_bars=96 if tf == "5m" else 48,
            )
        )

    # 15m EMA+ADX with stops (frequency bridge between 5m and 1h)
    for fast, slow, adx_thr, stop, take in itertools.product(
        (12, 20), (50, 100), (25, 30), (2.0, 2.5), (3.5, 4.5)
    ):
        trials.append(
            TrialSpec(
                f"EMAADX_{fast}_{slow}_a{adx_thr}_s{stop}_t{take}_15m",
                "trend",
                "15m",
                None,
                {"fast": fast, "slow": slow, "adx_thr": adx_thr},
                sig_ema_adx_params,
                stop_atr_mult=stop,
                take_atr_mult=take,
            )
        )

    # 1h donchian / keltner denser exits (already good frequency; refine)
    for entry, exit_n, stop, take in itertools.product(
        (40, 55, 80), (10, 15, 20), (2.5, 3.0), (4.0, 6.0)
    ):
        if exit_n >= entry:
            continue
        trials.append(
            TrialSpec(
                f"DON_{entry}_{exit_n}_s{stop}_t{take}_1h",
                "breakout",
                "1h",
                None,
                {"entry": entry, "exit": exit_n},
                sig_donchian_params,
                stop_atr_mult=stop,
                take_atr_mult=take,
            )
        )

    for length, mult, stop, take in itertools.product(
        (15, 20, 30), (2.0, 2.5, 3.0), (2.0, 2.5), (4.0, 5.0)
    ):
        trials.append(
            TrialSpec(
                f"KELT_{length}x{mult}_s{stop}_t{take}_1h",
                "breakout",
                "1h",
                None,
                {"len": length, "mult": mult},
                sig_keltner_break,
                stop_atr_mult=stop,
                take_atr_mult=take,
            )
        )

    logger.info("Freq search space size: %s trials", len(trials))
    return trials


def _execution_window(trades) -> tuple[str | None, str | None]:
    if not trades:
        return None, None
    first = min(t.entry_time for t in trades)
    last = max(t.exit_time for t in trades)
    return str(first), str(last)


def evaluate_trial(
    trial: TrialSpec,
    symbol: str,
    frames: dict[str, pd.DataFrame],
    funding: pd.DataFrame,
    cost: CostModel,
) -> dict | None:
    df = frames.get(trial.timeframe)
    if df is None or df.empty:
        return None
    htf = frames.get(trial.htf) if trial.htf else None
    if trial.htf and (htf is None or htf.empty):
        return None

    df = df.reset_index(drop=True)
    params = dict(trial.params)
    if trial.build is sig_funding_fade:
        params["_funding"] = funding

    signal = trial.build(df, htf, params)
    atr = ind.atr(df["high"], df["low"], df["close"], 14)

    def _run(slice_df: pd.DataFrame) -> object:
        if funding is not None and not funding.empty:
            t0, t1 = slice_df["timestamp"].iloc[0], slice_df["timestamp"].iloc[-1]
            fund = funding[(funding["timestamp"] >= t0) & (funding["timestamp"] <= t1)]
        else:
            fund = funding
        return run_backtest(
            slice_df,
            signal.reindex(slice_df.index).fillna(0),
            funding=fund,
            cost=cost,
            stop_atr_mult=trial.stop_atr_mult,
            take_atr_mult=trial.take_atr_mult,
            atr=atr.reindex(slice_df.index),
            max_hold_bars=trial.max_hold_bars,
        )

    full = _run(df)
    is_df, oos_df = walk_forward_split(df, 0.7)
    oos = _run(oos_df)
    first_ex, last_ex = _execution_window(full.trades)
    trades_n = int(full.metrics.get("trades", 0))
    # Relaxed min trades for swing systems
    m = dict(full.metrics)
    if trades_n >= 8:
        score = composite_score({**m, "trades": max(trades_n, 20)})
    else:
        score = composite_score(m)
    oos_m = dict(oos.metrics)
    if oos_m.get("trades", 0) >= 5:
        oos_score = composite_score({**oos_m, "trades": max(int(oos_m.get("trades", 0)), 20)})
        if oos_score > -900:
            score = 0.5 * score + 0.5 * oos_score

    notes = []
    if trades_n < 8:
        notes.append("low_trades")
    if m.get("total_return", 0) > 0:
        notes.append("net_positive")
    if oos_m.get("total_return", 0) > 0:
        notes.append("oos_positive")
    if abs(m.get("max_drawdown", 0)) > 0.4:
        notes.append("high_dd")

    return {
        "strategy_id": trial.strategy_id,
        "family": trial.family,
        "symbol": symbol,
        "timeframe": trial.timeframe,
        "params": {k: v for k, v in trial.params.items() if not str(k).startswith("_")},
        "total_return": m.get("total_return"),
        "oos_return": oos_m.get("total_return"),
        "max_drawdown": m.get("max_drawdown"),
        "sharpe": m.get("sharpe"),
        "profit_factor": m.get("profit_factor"),
        "win_rate": m.get("win_rate"),
        "score": score,
        "trades": trades_n,
        "first_execution_at": first_ex,
        "last_execution_at": last_ex,
        "notes": ",".join(notes) if notes else "ok",
        "metrics": m,
        "stop_atr_mult": trial.stop_atr_mult,
        "take_atr_mult": trial.take_atr_mult,
    }


def run_optimization(
    symbols: list[str],
    frames_by_symbol: dict[str, dict[str, pd.DataFrame]],
    funding_by_symbol: dict[str, pd.DataFrame],
    *,
    cost: CostModel | None = None,
    max_trials: int | None = None,
    space: str = "default",
    min_trades: int = 0,
) -> pd.DataFrame:
    cost = cost or CostModel()
    trials = build_freq_search_space() if space == "freq" else build_search_space()
    if max_trials is not None:
        trials = trials[:max_trials]
    run_id = str(uuid.uuid4())
    research_db.save_backtest_run(
        run_id=run_id,
        symbols=symbols,
        cost_taker_fee=cost.fee_rate,
        cost_slippage_bps=cost.slippage_bps,
        leverage=1.0,
        period_start=None,
        period_end=None,
        notes="optimize grid search",
        meta={"n_trials_per_symbol": len(trials)},
    )

    rows: list[dict] = []
    total = len(trials) * len(symbols)
    done = 0
    for symbol in symbols:
        frames = frames_by_symbol[symbol]
        funding = funding_by_symbol.get(symbol, pd.DataFrame())
        for trial in trials:
            done += 1
            if done % 25 == 0 or done == total:
                logger.info("Optimize progress %s/%s (%s)", done, total, trial.strategy_id)
            try:
                result = evaluate_trial(trial, symbol, frames, funding, cost)
            except Exception:
                logger.exception("Trial failed %s %s", trial.strategy_id, symbol)
                continue
            if result is None:
                continue
            rows.append(result)
            research_db.save_strategy_result(run_id, result)

    research_db.finish_backtest_run(run_id)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values(["total_return", "score"], ascending=False).reset_index(drop=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"_{space}" if space != "default" else ""
    df.to_csv(REPORTS_DIR / f"optimize_results{suffix}.csv", index=False)
    pos = df[df["total_return"] > 0].copy()
    pos.to_csv(REPORTS_DIR / f"optimize_positive{suffix}.csv", index=False)

    # Consensus: average across symbols for same strategy_id
    consensus = (
        df.groupby("strategy_id")
        .agg(
            family=("family", "first"),
            timeframe=("timeframe", "first"),
            mean_return=("total_return", "mean"),
            mean_oos=("oos_return", "mean"),
            mean_dd=("max_drawdown", "mean"),
            mean_sharpe=("sharpe", "mean"),
            mean_trades=("trades", "mean"),
            min_trades=("trades", "min"),
            symbols=("symbol", "nunique"),
            first_execution_at=("first_execution_at", "min"),
            last_execution_at=("last_execution_at", "max"),
            mean_score=("score", "mean"),
        )
        .reset_index()
        .sort_values(["mean_return", "mean_score"], ascending=False)
    )
    if min_trades > 0:
        consensus = consensus[consensus["min_trades"] >= min_trades].reset_index(drop=True)
    consensus.to_csv(REPORTS_DIR / f"optimize_consensus{suffix}.csv", index=False)

    # Both-symbol positive with frequency floor
    both_rows = []
    for sid, g in df.groupby("strategy_id"):
        if set(g["symbol"]) != {"BTCUSDT", "ETHUSDT"}:
            continue
        b = g[g["symbol"] == "BTCUSDT"].iloc[0]
        e = g[g["symbol"] == "ETHUSDT"].iloc[0]
        if (
            b["trades"] >= min_trades
            and e["trades"] >= min_trades
            and b["total_return"] > 0
            and e["total_return"] > 0
        ):
            both_rows.append(
                {
                    "strategy_id": sid,
                    "family": b["family"],
                    "timeframe": b["timeframe"],
                    "btc_return": b["total_return"],
                    "eth_return": e["total_return"],
                    "mean_return": (b["total_return"] + e["total_return"]) / 2,
                    "mean_oos": (b["oos_return"] + e["oos_return"]) / 2,
                    "mean_dd": (b["max_drawdown"] + e["max_drawdown"]) / 2,
                    "mean_trades": (b["trades"] + e["trades"]) / 2,
                    "first_execution_at": min(str(b["first_execution_at"]), str(e["first_execution_at"])),
                    "last_execution_at": max(str(b["last_execution_at"]), str(e["last_execution_at"])),
                }
            )
    both = pd.DataFrame(both_rows)
    if not both.empty:
        both = both.sort_values("mean_return", ascending=False)
        both.to_csv(REPORTS_DIR / f"optimize_both_positive{suffix}.csv", index=False)

    logger.info(
        "Positive rows: %s / %s; freq-filtered consensus=%s; both+freq=%s; top=%s",
        len(pos),
        len(df),
        len(consensus),
        len(both),
        consensus["mean_return"].iloc[0] if len(consensus) else None,
    )
    return consensus
