"""Walk-forward aware ranking and robustness scoring."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.research.backtest.engine import BacktestResult, run_backtest
from backend.research.config import CostModel
from backend.research.indicators import core as ind
from backend.research.strategies.base import StrategySpec


@dataclass(slots=True)
class RankedResult:
    strategy_id: str
    symbol: str
    family: str
    timeframe: str
    metrics_full: dict[str, float]
    metrics_is: dict[str, float]
    metrics_oos: dict[str, float]
    score: float
    notes: str
    trades: int = 0
    first_execution_at: str | None = None
    last_execution_at: str | None = None


def composite_score(m: dict[str, float]) -> float:
    """Higher is better. Penalize drawdown, reward return/sharpe/consistency."""
    if not m or m.get("trades", 0) < 8:
        return -999.0
    ret = m.get("total_return", 0.0)
    dd = abs(m.get("max_drawdown", 0.0))
    sharpe = m.get("sharpe", 0.0)
    pf = min(m.get("profit_factor", 0.0), 5.0)
    cons = m.get("consistency_30d", 0.0)
    calmar = m.get("calmar", 0.0)
    # Soft constraints
    if dd > 0.45 and ret <= 0:
        return -500.0 + ret
    if ret <= 0:
        return ret * 10 - dd * 5
    score = (
        1.5 * ret
        + 0.35 * sharpe
        + 0.25 * calmar
        + 0.15 * pf
        + 0.4 * cons
        - 1.2 * dd
    )
    return float(score)


def walk_forward_split(df: pd.DataFrame, is_frac: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = len(df)
    cut = int(n * is_frac)
    return df.iloc[:cut].copy(), df.iloc[cut:].copy()


def evaluate_strategy(
    spec: StrategySpec,
    symbol: str,
    frames: dict[str, pd.DataFrame],
    funding: pd.DataFrame,
    *,
    cost: CostModel | None = None,
) -> RankedResult | None:
    df = frames.get(spec.timeframe)
    if df is None or df.empty:
        return None
    htf = frames.get(spec.htf) if spec.htf else None
    if spec.htf and (htf is None or htf.empty):
        return None

    df = df.reset_index(drop=True)
    signal = spec.build_signal(df, htf)
    atr = ind.atr(df["high"], df["low"], df["close"], 14)

    def _run(slice_df: pd.DataFrame, sig: pd.Series, atr_s: pd.Series) -> BacktestResult:
        # Align funding to slice window
        if funding is not None and not funding.empty:
            t0, t1 = slice_df["timestamp"].iloc[0], slice_df["timestamp"].iloc[-1]
            fund = funding[(funding["timestamp"] >= t0) & (funding["timestamp"] <= t1)]
        else:
            fund = funding
        return run_backtest(
            slice_df,
            sig.reindex(slice_df.index).fillna(0),
            funding=fund,
            cost=cost,
            stop_atr_mult=spec.stop_atr_mult,
            take_atr_mult=spec.take_atr_mult,
            atr=atr_s.reindex(slice_df.index),
            max_hold_bars=spec.max_hold_bars,
        )

    full = _run(df, signal, atr)
    is_df, oos_df = walk_forward_split(df, 0.7)
    is_res = _run(is_df, signal.loc[is_df.index], atr.loc[is_df.index])
    oos_res = _run(oos_df, signal.loc[oos_df.index], atr.loc[oos_df.index])

    # Robustness: OOS should not collapse vs IS
    is_ret = is_res.metrics.get("total_return", 0.0)
    oos_ret = oos_res.metrics.get("total_return", 0.0)
    notes = []
    if is_ret > 0.05 and oos_ret < 0:
        notes.append("oos_breakdown")
    if full.metrics.get("trades", 0) < 8:
        notes.append("low_trades")
    if abs(full.metrics.get("max_drawdown", 0)) > 0.4:
        notes.append("high_dd")
    if full.metrics.get("total_return", 0) > 0:
        notes.append("net_positive")

    score = composite_score(full.metrics)
    # Blend OOS into score
    oos_score = composite_score(oos_res.metrics)
    if oos_score > -900:
        score = 0.55 * score + 0.45 * oos_score
    if "oos_breakdown" in notes:
        score -= 0.5

    first_ex = last_ex = None
    if full.trades:
        first_ex = str(min(t.entry_time for t in full.trades))
        last_ex = str(max(t.exit_time for t in full.trades))

    return RankedResult(
        strategy_id=spec.id,
        symbol=symbol,
        family=spec.family,
        timeframe=spec.timeframe,
        metrics_full=full.metrics,
        metrics_is=is_res.metrics,
        metrics_oos=oos_res.metrics,
        score=score,
        notes=",".join(notes) if notes else "ok",
        trades=int(full.metrics.get("trades", 0)),
        first_execution_at=first_ex,
        last_execution_at=last_ex,
    )


def results_to_frame(rows: list[RankedResult]) -> pd.DataFrame:
    records = []
    for r in rows:
        rec = {
            "strategy_id": r.strategy_id,
            "symbol": r.symbol,
            "family": r.family,
            "timeframe": r.timeframe,
            "score": r.score,
            "notes": r.notes,
            "trades": r.trades,
            "first_execution_at": r.first_execution_at,
            "last_execution_at": r.last_execution_at,
        }
        for prefix, metrics in (
            ("full", r.metrics_full),
            ("is", r.metrics_is),
            ("oos", r.metrics_oos),
        ):
            for k, v in metrics.items():
                rec[f"{prefix}_{k}"] = v
        records.append(rec)
    df = pd.DataFrame(records)
    if df.empty:
        return df
    return df.sort_values("score", ascending=False).reset_index(drop=True)


def cross_symbol_consensus(ranked: pd.DataFrame) -> pd.DataFrame:
    """Average score across symbols; require coverage on BTC and ETH."""
    if ranked.empty:
        return ranked
    pivot = ranked.pivot_table(
        index="strategy_id",
        columns="symbol",
        values="score",
        aggfunc="mean",
    )
    out = ranked.groupby("strategy_id").agg(
        family=("family", "first"),
        timeframe=("timeframe", "first"),
        mean_score=("score", "mean"),
        median_score=("score", "median"),
        mean_full_return=("full_total_return", "mean"),
        mean_oos_return=("oos_total_return", "mean"),
        mean_max_dd=("full_max_drawdown", "mean"),
        mean_sharpe=("full_sharpe", "mean"),
        mean_trades=("trades", "mean"),
        min_trades=("trades", "min"),
        first_execution_at=("first_execution_at", "min"),
        last_execution_at=("last_execution_at", "max"),
        symbols=("symbol", "nunique"),
    )
    for sym in ("BTCUSDT", "ETHUSDT"):
        if sym in pivot.columns:
            out[f"score_{sym}"] = pivot[sym]
    out = out.sort_values(
        ["mean_full_return", "mean_score"], ascending=False
    )
    return out.reset_index()
