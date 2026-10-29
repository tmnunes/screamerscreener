"""Perpetual futures backtester: long/short, fees, slippage, funding, 1x default."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from backend.research.config import CostModel, DEFAULT_INITIAL_EQUITY, DEFAULT_LEVERAGE

Side = Literal["flat", "long", "short"]


@dataclass(slots=True)
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: str
    entry_price: float
    exit_price: float
    qty: float
    pnl: float
    fees: float
    funding: float
    bars_held: int
    exit_reason: str


@dataclass(slots=True)
class BacktestResult:
    equity_curve: pd.Series
    trades: list[Trade]
    metrics: dict[str, float]
    meta: dict = field(default_factory=dict)


def _apply_slippage(price: float, side: str, is_entry: bool, slip: float) -> float:
    # Adverse fill: buy higher, sell lower
    if side == "long":
        return price * (1 + slip) if is_entry else price * (1 - slip)
    return price * (1 - slip) if is_entry else price * (1 + slip)


def run_backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    *,
    funding: pd.DataFrame | None = None,
    cost: CostModel | None = None,
    leverage: float = DEFAULT_LEVERAGE,
    initial_equity: float = DEFAULT_INITIAL_EQUITY,
    stop_atr_mult: float | None = None,
    take_atr_mult: float | None = None,
    atr: pd.Series | None = None,
    max_hold_bars: int | None = None,
    allow_flip: bool = True,
) -> BacktestResult:
    """Execute rule-based signals on OHLCV.

    ``signal`` values at bar i are assumed known at bar i close.
    Entries/exits fill at bar i+1 open (no look-ahead on same-bar close fills).
    signal: +1 long, -1 short, 0 flat/exit.
    """
    cost = cost or CostModel()
    if len(df) < 3:
        empty = pd.Series(dtype=float)
        return BacktestResult(empty, [], {}, {"reason": "insufficient_bars"})

    opens = df["open"].to_numpy(float)
    highs = df["high"].to_numpy(float)
    lows = df["low"].to_numpy(float)
    closes = df["close"].to_numpy(float)
    times = pd.to_datetime(df["timestamp"], utc=True)
    sig = signal.reindex(df.index).fillna(0).astype(int).to_numpy()
    atr_vals = atr.reindex(df.index).to_numpy(float) if atr is not None else None

    funding_events: list[tuple[pd.Timestamp, float]] = []
    if funding is not None and not funding.empty:
        f = funding.sort_values("timestamp")
        funding_events = list(
            zip(
                pd.to_datetime(f["timestamp"], utc=True),
                f["funding_rate"].astype(float),
            )
        )
    f_idx = 0

    equity = initial_equity
    cash_pnl = 0.0
    side: Side = "flat"
    qty = 0.0
    entry_price = 0.0
    entry_i = -1
    stop = np.nan
    take = np.nan
    trade_funding = 0.0
    trade_fees = 0.0
    trades: list[Trade] = []
    equity_path = np.full(len(df), np.nan)

    fee_rate = cost.fee_rate
    slip = cost.slippage_rate

    def position_notional(price: float) -> float:
        return abs(qty) * price

    def unrealized(price: float) -> float:
        if side == "flat" or qty == 0:
            return 0.0
        if side == "long":
            return qty * (price - entry_price)
        return qty * (entry_price - price)

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal equity, cash_pnl, side, qty, entry_price, entry_i
        nonlocal trade_funding, trade_fees, stop, take
        if side == "flat":
            return
        fill = _apply_slippage(price, side, is_entry=False, slip=slip)
        fee = position_notional(fill) * fee_rate
        if side == "long":
            pnl = qty * (fill - entry_price) - fee
        else:
            pnl = qty * (entry_price - fill) - fee
        pnl += trade_funding
        cash_pnl += pnl
        equity = initial_equity + cash_pnl
        trades.append(
            Trade(
                entry_time=times.iloc[entry_i],
                exit_time=times.iloc[i],
                side=side,
                entry_price=entry_price,
                exit_price=fill,
                qty=qty,
                pnl=pnl,
                fees=trade_fees + fee,
                funding=trade_funding,
                bars_held=i - entry_i,
                exit_reason=reason,
            )
        )
        side = "flat"
        qty = 0.0
        entry_price = 0.0
        entry_i = -1
        stop = np.nan
        take = np.nan
        trade_funding = 0.0
        trade_fees = 0.0

    def open_position(i: int, new_side: Side) -> None:
        nonlocal side, qty, entry_price, entry_i, stop, take, trade_fees, equity, cash_pnl
        price = opens[i]
        fill = _apply_slippage(price, new_side, is_entry=True, slip=slip)
        notional = max(equity, 0.0) * leverage
        if notional <= 0 or fill <= 0:
            return
        qty = notional / fill
        fee = notional * fee_rate
        trade_fees = fee
        cash_pnl -= fee
        equity = initial_equity + cash_pnl
        side = new_side
        entry_price = fill
        entry_i = i
        if stop_atr_mult is not None and atr_vals is not None and not np.isnan(atr_vals[i]):
            dist = stop_atr_mult * atr_vals[i]
            stop = fill - dist if new_side == "long" else fill + dist
        if take_atr_mult is not None and atr_vals is not None and not np.isnan(atr_vals[i]):
            dist = take_atr_mult * atr_vals[i]
            take = fill + dist if new_side == "long" else fill - dist

    # Signal at i close → execute at i+1 open (including flat exits)
    pending: int | None = None

    for i in range(len(df)):
        # Funding at/before this bar open while a position is open
        t = times.iloc[i]
        while f_idx < len(funding_events) and funding_events[f_idx][0] <= t:
            _ft, fr = funding_events[f_idx]
            f_idx += 1
            if side == "flat":
                continue
            mark = opens[i]
            payment = -qty * mark * fr if side == "long" else qty * mark * fr
            trade_funding += payment
            cash_pnl += payment
            equity = initial_equity + cash_pnl

        # Intrabar stop / take using high/low (if both hit, assume stop first)
        if side != "flat" and i > entry_i:
            hit_stop = False
            hit_take = False
            if not np.isnan(stop):
                if side == "long" and lows[i] <= stop:
                    hit_stop = True
                if side == "short" and highs[i] >= stop:
                    hit_stop = True
            if not np.isnan(take):
                if side == "long" and highs[i] >= take:
                    hit_take = True
                if side == "short" and lows[i] <= take:
                    hit_take = True
            if hit_stop:
                close_position(i, float(stop), "stop")
            elif hit_take:
                close_position(i, float(take), "take")

        if max_hold_bars is not None and side != "flat" and (i - entry_i) >= max_hold_bars:
            close_position(i, opens[i], "time_stop")

        # Execute pending target from previous bar close
        if pending is not None and i > 0:
            desired: Side = (
                "long" if pending > 0 else "short" if pending < 0 else "flat"
            )
            if desired == "flat":
                close_position(i, opens[i], "signal_flat")
            elif side == "flat":
                open_position(i, desired)
            elif side != desired:
                if allow_flip:
                    close_position(i, opens[i], "flip")
                    open_position(i, desired)
                else:
                    close_position(i, opens[i], "signal_exit")
            pending = None

        equity_path[i] = equity + unrealized(closes[i])

        if i < len(df) - 1:
            pending = int(sig[i])

    if side != "flat":
        close_position(len(df) - 1, closes[-1], "eod")

    curve = pd.Series(equity_path, index=times, name="equity").ffill()
    metrics = compute_metrics(curve, trades, initial_equity)
    return BacktestResult(curve, trades, metrics)


def compute_metrics(
    equity: pd.Series,
    trades: list[Trade],
    initial_equity: float,
) -> dict[str, float]:
    if equity.empty:
        return {}
    rets = equity.pct_change().dropna()
    total_return = float(equity.iloc[-1] / initial_equity - 1)
    peak = equity.cummax()
    dd = equity / peak - 1
    max_dd = float(dd.min()) if len(dd) else 0.0
    # Annualize assuming 5m bars ~ 105120 bars/year
    bars_per_year = 365.25 * 24 * 12
    if len(rets) > 1:
        vol = float(rets.std() * np.sqrt(bars_per_year))
        mean = float(rets.mean() * bars_per_year)
        sharpe = mean / vol if vol > 1e-12 else 0.0
    else:
        vol = 0.0
        sharpe = 0.0
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    gross_profit = sum(t.pnl for t in wins) if wins else 0.0
    gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 1e-12 else float("inf") if gross_profit > 0 else 0.0
    avg_trade = float(np.mean([t.pnl for t in trades])) if trades else 0.0
    win_rate = len(wins) / len(trades) if trades else 0.0
    # Calmar-like
    calmar = total_return / abs(max_dd) if max_dd < 0 else 0.0
    # Consistency: fraction of rolling 30d windows with positive return
    if len(equity) > 30 * 24 * 12:
        window = 30 * 24 * 12
        roll = equity.pct_change(window).dropna()
        consistency = float((roll > 0).mean()) if len(roll) else 0.0
    else:
        consistency = float("nan")
    return {
        "total_return": total_return,
        "max_drawdown": max_dd,
        "sharpe": float(sharpe),
        "volatility": vol,
        "trades": float(len(trades)),
        "win_rate": win_rate,
        "profit_factor": float(profit_factor) if np.isfinite(profit_factor) else 99.0,
        "avg_trade_pnl": avg_trade,
        "calmar": float(calmar),
        "consistency_30d": consistency if consistency == consistency else 0.0,
        "final_equity": float(equity.iloc[-1]),
        "fees_paid": float(sum(t.fees for t in trades)),
        "funding_pnl": float(sum(t.funding for t in trades)),
    }
