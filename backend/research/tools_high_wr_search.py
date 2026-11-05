"""Search for WR>=70% and YTD>=150% on ETHUSDT (fees on, 1x).

Two-stage: (1) screen signals with fixed high-WR risk, (2) refine stop/take.
  .venv/bin/python -m backend.research.tools_high_wr_search
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.research.backtest.engine import run_backtest
from backend.research.config import CostModel, REPORTS_DIR
from backend.research.data.store import load_dataset, load_funding_normalized
from backend.research.indicators import core as ind

START = pd.Timestamp("2026-01-01", tz="UTC")
END = pd.Timestamp("2026-10-29 23:59:59", tz="UTC")
MIN_YTD_TRADES = 25


@dataclass
class Hit:
    sid: str
    family: str
    ytd: float
    wr: float
    trades: int
    full: float
    dd: float
    pf: float
    full_wr: float


def ytd_from_result(df: pd.DataFrame, res) -> dict | None:
    eq = res.equity_curve.copy()
    eq.index = pd.to_datetime(df["timestamp"], utc=True)
    eqy = eq[(eq.index >= START) & (eq.index <= END)]
    if len(eqy) < 2:
        return None
    ytd = float(eqy.iloc[-1] / eqy.iloc[0] - 1)
    ty = [t for t in res.trades if START <= t.entry_time <= END]
    if len(ty) < MIN_YTD_TRADES:
        return None
    wr = sum(1 for t in ty if t.pnl > 0) / len(ty)
    m = res.metrics
    return {
        "ytd": ytd,
        "wr": wr,
        "trades": len(ty),
        "full": float(m["total_return"]),
        "dd": float(m["max_drawdown"]),
        "pf": float(m.get("profit_factor") or 0),
        "full_wr": float(m["win_rate"]),
    }


def state_machine(long_entry, short_entry, long_exit, short_exit) -> pd.Series:
    n = len(long_entry)
    out = np.zeros(n, dtype=np.int8)
    state = 0
    le = long_entry.fillna(False).to_numpy()
    se = short_entry.fillna(False).to_numpy()
    lx = long_exit.fillna(False).to_numpy()
    sx = short_exit.fillna(False).to_numpy()
    for i in range(n):
        if state == 0:
            if le[i]:
                state = 1
            elif se[i]:
                state = -1
        elif state == 1:
            if lx[i]:
                state = 0
        elif state == -1:
            if sx[i]:
                state = 0
        out[i] = state
    return pd.Series(out)


def run(df, fund, atr_s, cost, sig, stop, take):
    return run_backtest(
        df, sig, funding=fund, stop_atr_mult=stop, take_atr_mult=take, atr=atr_s, cost=cost
    )


def sig_rsi_bounce(df, trend_len, rsi_lo, rsi_ex, adx_thr, long_only):
    close = df["close"]
    trend = ind.ema(close, trend_len)
    r = ind.rsi(close, 14)
    adx, plus, minus = ind.adx_di(df["high"], df["low"], close, 14)
    long_entry = (close > trend) & (adx >= adx_thr) & (plus > minus) & (r <= rsi_lo)
    short_entry = (close < trend) & (adx >= adx_thr) & (minus > plus) & (r >= 100 - rsi_lo)
    if long_only:
        short_entry = pd.Series(False, index=df.index)
    long_exit = (r >= rsi_ex) | (close < trend)
    short_exit = (r <= 100 - rsi_ex) | (close > trend)
    return state_machine(long_entry, short_entry, long_exit, short_exit)


def sig_bb_mr(df, bb_len, bb_mult, rsi_lo, adx_max):
    close = df["close"]
    mid, up, lo, _ = ind.bollinger(close, bb_len, bb_mult)
    r = ind.rsi(close, 14)
    adx, _, _ = ind.adx_di(df["high"], df["low"], close, 14)
    quiet = adx <= adx_max
    long_entry = quiet & (close < lo) & (r <= rsi_lo)
    short_entry = quiet & (close > up) & (r >= 100 - rsi_lo)
    return state_machine(long_entry, short_entry, close >= mid, close <= mid)


def sig_stoch_bb(df, bb_len, bb_mult, k_lo, k_ex, adx_max):
    close = df["close"]
    k, _ = ind.stochastic_rsi(close, 14, 14, 3, 3)
    mid, up, lo, _ = ind.bollinger(close, bb_len, bb_mult)
    adx, _, _ = ind.adx_di(df["high"], df["low"], close, 14)
    quiet = adx <= adx_max
    long_entry = quiet & (k <= k_lo) & (close <= lo)
    short_entry = quiet & (k >= 100 - k_lo) & (close >= up)
    long_exit = (k >= k_ex) | (close >= mid)
    short_exit = (k <= 100 - k_ex) | (close <= mid)
    return state_machine(long_entry, short_entry, long_exit, short_exit)


def sig_pull(df, fast, slow, rsi_on):
    close = df["close"]
    e_fast = ind.ema(close, fast)
    e_slow = ind.ema(close, slow)
    r = ind.rsi(close, 14)
    touched = (df["low"] <= e_fast) | (df["low"].shift(1) <= e_fast.shift(1))
    long_entry = (close > e_slow) & touched & (close > e_fast) & (r >= rsi_on)
    long_exit = (close < e_fast) | (close < e_slow)
    short_entry = pd.Series(False, index=df.index)
    short_exit = pd.Series(False, index=df.index)
    return state_machine(long_entry, short_entry, long_exit, short_exit)


def sig_macd(df, trend_len, rsi_floor):
    close = df["close"]
    trend = ind.ema(close, trend_len)
    line, signal, hist = ind.macd(close)
    r = ind.rsi(close, 14)
    long_entry = (close > trend) & (line > signal) & (hist > hist.shift(1)) & (r >= rsi_floor) & (r <= 68)
    short_entry = (close < trend) & (line < signal) & (hist < hist.shift(1)) & (r <= 100 - rsi_floor) & (r >= 32)
    long_exit = (line < signal) | (close < trend)
    short_exit = (line > signal) | (close > trend)
    return state_machine(long_entry, short_entry, long_exit, short_exit)


def sig_kelt(df, length, mult):
    mid, up, lo = ind.keltner(df["high"], df["low"], df["close"], length, 10, mult)
    return state_machine(df["close"] > up.shift(1), df["close"] < lo.shift(1), df["close"] < mid, df["close"] > mid)


def sig_di_cross(df, adx_thr, trend_len):
    """+DI/-DI cross with ADX filter — often higher WR than raw breakouts."""
    close = df["close"]
    trend = ind.ema(close, trend_len)
    adx, plus, minus = ind.adx_di(df["high"], df["low"], close, 14)
    plus_above = plus > minus
    cross_up = plus_above & ~plus_above.shift(1).fillna(False)
    cross_dn = (~plus_above) & plus_above.shift(1).fillna(False)
    long_entry = cross_up & (adx >= adx_thr) & (close > trend)
    short_entry = cross_dn & (adx >= adx_thr) & (close < trend)
    long_exit = cross_dn | (plus < minus) | (close < trend)
    short_exit = cross_up | (plus > minus) | (close > trend)
    return state_machine(long_entry, short_entry, long_exit, short_exit)


def build_signal_bank(df: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    bank: list[tuple[str, str, pd.Series]] = []

    for trend, rsi_lo, rsi_ex, adx_thr, long_only in itertools.product(
        (100, 200), (30, 35, 40), (55, 60, 65), (20, 25), (True, False)
    ):
        if rsi_ex <= rsi_lo + 5:
            continue
        tag = "L" if long_only else "LS"
        sid = f"RSIBOUNCE_{tag}_e{trend}_lo{rsi_lo}_ex{rsi_ex}_a{adx_thr}"
        bank.append(("RSI", sid, sig_rsi_bounce(df, trend, rsi_lo, rsi_ex, adx_thr, long_only)))

    for bb_len, bb_mult, rsi_lo, adx_max in itertools.product(
        (20, 30), (2.0, 2.5), (30, 35), (20, 25, 30)
    ):
        sid = f"MR_bb{bb_len}x{bb_mult}_r{rsi_lo}_a{adx_max}"
        bank.append(("MR", sid, sig_bb_mr(df, bb_len, bb_mult, rsi_lo, adx_max)))

    for bb_len, k_lo, k_ex, adx_max in itertools.product(
        (20, 30), (15, 20), (55, 65), (20, 25)
    ):
        sid = f"STOCH_bb{bb_len}_k{k_lo}_ex{k_ex}_a{adx_max}"
        bank.append(("STOCH", sid, sig_stoch_bb(df, bb_len, 2.0, k_lo, k_ex, adx_max)))

    for fast, slow, rsi_on in itertools.product((12, 20), (100, 200), (50, 55)):
        sid = f"PULL_f{fast}_s{slow}_r{rsi_on}"
        bank.append(("PULL", sid, sig_pull(df, fast, slow, rsi_on)))

    for trend, rsi_floor in itertools.product((100, 200), (50, 55)):
        sid = f"MACD_e{trend}_r{rsi_floor}"
        bank.append(("MACD", sid, sig_macd(df, trend, rsi_floor)))

    for length, mult in itertools.product((15, 20, 30), (2.5, 3.0)):
        sid = f"KELT_{length}x{mult}"
        bank.append(("KELT", sid, sig_kelt(df, length, mult)))

    for adx_thr, trend in itertools.product((20, 25, 30), (50, 100, 200)):
        sid = f"DI_a{adx_thr}_e{trend}"
        bank.append(("DI", sid, sig_di_cross(df, adx_thr, trend)))

    return bank


def main() -> None:
    t0 = time.time()
    cost = CostModel()
    hits: list[Hit] = []

    # Stage-1 risk profiles aimed at high WR
    screen_risks = [(3.0, 1.0), (3.5, 1.2), (2.5, 1.0), (3.0, 1.5), (2.0, 1.0)]
    # Stage-2 refine around survivors
    refine_stops = (2.0, 2.5, 3.0, 3.5, 4.0)
    refine_takes = (0.8, 1.0, 1.2, 1.5, 2.0, 2.5)

    for tf in ("1h", "15m"):
        df, _ = load_dataset("ETHUSDT", tf)
        fund = load_funding_normalized("ETHUSDT")
        atr_s = ind.atr(df["high"], df["low"], df["close"], 14)
        print(f"\n=== {tf} bars={len(df)} building signals ===")
        bank = build_signal_bank(df)
        print(f"  signals: {len(bank)}")

        survivors: list[tuple[str, str, pd.Series, float, float]] = []
        for fam, sid, sig in bank:
            best_wr = -1.0
            best_pair = None
            best_st = None
            for stop, take in screen_risks:
                res = run(df, fund, atr_s, cost, sig, stop, take)
                st = ytd_from_result(df, res)
                if st is None:
                    continue
                # keep if interesting on either axis
                if st["wr"] >= 0.62 or (st["wr"] >= 0.55 and st["ytd"] >= 0.8):
                    if st["wr"] > best_wr:
                        best_wr = st["wr"]
                        best_pair = (stop, take)
                        best_st = st
            if best_pair and best_st:
                survivors.append((fam, sid, sig, best_pair[0], best_pair[1]))
                hits.append(
                    Hit(
                        sid=f"{sid}_s{best_pair[0]}_t{best_pair[1]}_{tf}",
                        family=fam,
                        **best_st,
                    )
                )

        print(f"  stage1 survivors: {len(survivors)} ({time.time()-t0:.0f}s)")

        for fam, sid, sig, _s, _t in survivors:
            for stop, take in itertools.product(refine_stops, refine_takes):
                res = run(df, fund, atr_s, cost, sig, stop, take)
                st = ytd_from_result(df, res)
                if st is None:
                    continue
                if st["wr"] < 0.60 and st["ytd"] < 1.0:
                    continue
                hits.append(Hit(sid=f"{sid}_s{stop}_t{take}_{tf}", family=fam, **st))

        print(f"  total hits so far: {len(hits)} ({time.time()-t0:.0f}s)")

    # Dedup keep best ytd per sid
    best: dict[str, Hit] = {}
    for h in hits:
        prev = best.get(h.sid)
        if prev is None or (h.ytd, h.wr) > (prev.ytd, prev.wr):
            best[h.sid] = h
    hits = list(best.values())

    strict = [h for h in hits if h.wr >= 0.70 and h.ytd >= 1.50]
    ranked = sorted(
        hits,
        key=lambda h: (max(0.0, 0.70 - h.wr) + max(0.0, 1.50 - h.ytd), -h.wr, -h.ytd),
    )

    lines = [
        "# High-WR / High-YTD search — ETHUSDT",
        f"Elapsed: {time.time()-t0:.0f}s | unique candidates: {len(hits)}",
        f"STRICT (WR>=70% & YTD>=150%): {len(strict)}",
        f"WR>=70%: {sum(1 for h in hits if h.wr >= 0.70)} | YTD>=150%: {sum(1 for h in hits if h.ytd >= 1.50)}",
        "",
        "## STRICT",
    ]
    for h in sorted(strict, key=lambda x: (-x.ytd, -x.wr))[:50]:
        lines.append(
            f"- `{h.sid}` YTD={h.ytd:+.0%} WR={h.wr:.0%} n={h.trades} "
            f"FULL={h.full:+.0%} dd={h.dd:.0%} pf={h.pf:.2f} fullWR={h.full_wr:.0%}"
        )
    lines += ["", "## Closest to target (top 40)"]
    for h in ranked[:40]:
        flag = (
            "HIT"
            if h.wr >= 0.70 and h.ytd >= 1.50
            else ("WR" if h.wr >= 0.70 else ("YTD" if h.ytd >= 1.50 else ""))
        )
        lines.append(
            f"- [{flag}] `{h.sid}` YTD={h.ytd:+.0%} WR={h.wr:.0%} n={h.trades} "
            f"FULL={h.full:+.0%} dd={h.dd:.0%} pf={h.pf:.2f}"
        )
    lines += ["", "## Best WR with YTD>=100%"]
    for h in sorted([h for h in hits if h.ytd >= 1.0], key=lambda x: (-x.wr, -x.ytd))[:30]:
        lines.append(f"- `{h.sid}` YTD={h.ytd:+.0%} WR={h.wr:.0%} n={h.trades} FULL={h.full:+.0%} dd={h.dd:.0%}")
    lines += ["", "## Best YTD with WR>=65%"]
    for h in sorted([h for h in hits if h.wr >= 0.65], key=lambda x: (-x.ytd, -x.wr))[:30]:
        lines.append(f"- `{h.sid}` YTD={h.ytd:+.0%} WR={h.wr:.0%} n={h.trades} FULL={h.full:+.0%} dd={h.dd:.0%}")

    text = "\n".join(lines)
    path = REPORTS_DIR / "high_wr_search.md"
    path.write_text(text)
    pd.DataFrame([h.__dict__ for h in ranked]).to_csv(REPORTS_DIR / "high_wr_search.csv", index=False)
    print("\n" + text)
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
