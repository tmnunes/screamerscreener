"""Traffic-light scoring for secondary indicators at trigger time.

Informational only — never modifies Vortex LONG / SHORT / STOP triggers.

For each trigger type, green means secondary context *supports* the signal,
red means it *contradicts* it, neutral is inconclusive.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Signal = Literal["green", "red", "neutral"]


@dataclass(frozen=True, slots=True)
class IndicatorSignal:
    key: str
    label: str
    category: str
    signal: Signal
    hint: str


@dataclass(frozen=True, slots=True)
class SecondarySignalsSummary:
    overall: Signal
    score: float
    green: int
    red: int
    neutral: int
    categories: dict[str, Signal]
    indicators: tuple[IndicatorSignal, ...]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["indicators"] = [asdict(i) for i in self.indicators]
        return data


def _sig(g: bool, r: bool) -> Signal:
    if g and not r:
        return "green"
    if r and not g:
        return "red"
    return "neutral"


def _flip(s: Signal) -> Signal:
    if s == "green":
        return "red"
    if s == "red":
        return "green"
    return "neutral"


def _num(row: dict[str, Any], key: str) -> float | None:
    v = row.get(key)
    if v is None:
        return None
    return float(v)


def _bool(row: dict[str, Any], key: str) -> bool | None:
    v = row.get(key)
    if v is None:
        return None
    return bool(v)


def _evaluate_rules(
    *,
    trigger_type: str,
    price: float,
    row: dict[str, Any],
    regime: dict[str, Any] | None,
) -> list[IndicatorSignal]:
    """Return per-indicator traffic lights for one trigger snapshot."""
    long_bias = trigger_type == "LONG"
    short_bias = trigger_type == "SHORT"
    stop_bias = trigger_type == "STOP"

    ema20 = _num(row, "ema20")
    ema50 = _num(row, "ema50")
    ema200 = _num(row, "ema200")
    sma200 = _num(row, "sma200")
    rsi = _num(row, "rsi14")
    macd = _num(row, "macd")
    macd_sig = _num(row, "macd_signal")
    macd_hist = _num(row, "macd_hist")
    roc = _num(row, "roc14")
    stoch_k = _num(row, "stoch_k")
    stoch_d = _num(row, "stoch_d")
    rel_vol = _num(row, "relative_volume")
    adx = _num(row, "adx14")
    br20 = _bool(row, "breakout_20d")
    br50 = _bool(row, "breakout_50d")
    dist52 = _num(row, "dist_52w_high")

    signals: list[IndicatorSignal] = []

    def add(key: str, label: str, category: str, bullish: bool, bearish: bool, hint: str) -> None:
        raw = _sig(bullish, bearish)
        if short_bias:
            sig = _flip(raw)
        elif stop_bias:
            # STOP: favour weakening / exit-friendly readings
            if category in {"MOMENTUM", "TREND"}:
                sig = raw if raw != "green" else "neutral"
                if bearish and not bullish:
                    sig = "green"
            else:
                sig = raw if raw == "neutral" else ("green" if raw == "red" else "neutral")
        else:
            sig = raw
        signals.append(IndicatorSignal(key, label, category, sig, hint))

    # TREND
    if ema20 is not None and ema50 is not None:
        add(
            "ema_stack",
            "EMA stack",
            "TREND",
            price > ema20 and ema20 > ema50,
            price < ema20 and ema20 < ema50,
            f"price {price:.2f} vs EMA20/50",
        )
    if sma200 is not None:
        add(
            "sma200",
            "SMA200",
            "TREND",
            price > sma200,
            price < sma200,
            f"price vs SMA200 {sma200:.2f}",
        )
    if adx is not None and macd is not None:
        add(
            "adx_trend",
            "ADX trend",
            "TREND",
            adx >= 25 and macd > 0,
            adx >= 25 and macd < 0,
            f"ADX {adx:.1f}",
        )

    # MOMENTUM
    if rsi is not None:
        add("rsi14", "RSI14", "MOMENTUM", rsi >= 55, rsi <= 45, f"RSI {rsi:.1f}")
    if macd is not None and macd_sig is not None:
        add(
            "macd",
            "MACD",
            "MOMENTUM",
            macd > macd_sig,
            macd < macd_sig,
            "MACD vs signal",
        )
    if macd_hist is not None:
        add(
            "macd_hist",
            "MACD hist",
            "MOMENTUM",
            macd_hist > 0,
            macd_hist < 0,
            f"hist {macd_hist:.4f}",
        )
    if roc is not None:
        add("roc14", "ROC14", "MOMENTUM", roc > 0, roc < 0, f"ROC {roc:.2f}%")
    if stoch_k is not None and stoch_d is not None:
        add(
            "stoch",
            "Stochastic",
            "MOMENTUM",
            stoch_k > stoch_d and stoch_k >= 50,
            stoch_k < stoch_d and stoch_k <= 50,
            f"K {stoch_k:.1f} / D {stoch_d:.1f}",
        )

    # VOLUME
    if rel_vol is not None:
        add(
            "rel_vol",
            "Rel. volume",
            "VOLUME",
            rel_vol >= 1.1,
            rel_vol <= 0.8,
            f"{rel_vol:.2f}x avg",
        )

    # VOLATILITY — direction-neutral; high ATR = caution
    atr_pct = _num(row, "atr_pct")
    if atr_pct is not None:
        add(
            "atr_pct",
            "ATR%",
            "VOLATILITY",
            atr_pct <= 2.5,
            atr_pct >= 4.0,
            f"ATR {atr_pct:.2f}%",
        )

    # PRICE ACTION
    if br20 is not None:
        add("breakout_20d", "20D breakout", "PRICE ACTION", br20, False, "20-day high break")
    if br50 is not None:
        add("breakout_50d", "50D breakout", "PRICE ACTION", br50, False, "50-day high break")
    if dist52 is not None:
        add(
            "dist_52w",
            "52W high",
            "PRICE ACTION",
            dist52 >= -0.05,
            dist52 <= -0.20,
            f"{dist52 * 100:.1f}% from high",
        )

    # MARKET REGIME
    if regime:
        spy = regime.get("spy_above_sma200")
        if spy is not None:
            add(
                "spy_regime",
                "SPY > SMA200",
                "MARKET REGIME",
                bool(spy),
                not bool(spy),
                "US broad market",
            )
        qqq = regime.get("qqq_above_sma200")
        if qqq is not None:
            add(
                "qqq_regime",
                "QQQ > SMA200",
                "MARKET REGIME",
                bool(qqq),
                not bool(qqq),
                "US growth / tech",
            )

    return signals


def summarize_signals(indicators: list[IndicatorSignal]) -> SecondarySignalsSummary:
    if not indicators:
        return SecondarySignalsSummary(
            overall="neutral",
            score=0.0,
            green=0,
            red=0,
            neutral=0,
            categories={},
            indicators=(),
        )

    green = sum(1 for i in indicators if i.signal == "green")
    red = sum(1 for i in indicators if i.signal == "red")
    neutral = sum(1 for i in indicators if i.signal == "neutral")
    total = len(indicators)
    score = (green - red) / total

    if score >= 0.25:
        overall: Signal = "green"
    elif score <= -0.25:
        overall = "red"
    else:
        overall = "neutral"

    categories: dict[str, Signal] = {}
    by_cat: dict[str, list[IndicatorSignal]] = {}
    for ind in indicators:
        by_cat.setdefault(ind.category, []).append(ind)

    for cat, items in by_cat.items():
        g = sum(1 for i in items if i.signal == "green")
        r = sum(1 for i in items if i.signal == "red")
        cat_score = (g - r) / len(items)
        if cat_score >= 0.34:
            categories[cat] = "green"
        elif cat_score <= -0.34:
            categories[cat] = "red"
        else:
            categories[cat] = "neutral"

    return SecondarySignalsSummary(
        overall=overall,
        score=round(score, 3),
        green=green,
        red=red,
        neutral=neutral,
        categories=categories,
        indicators=tuple(indicators),
    )


def evaluate_secondary_signals(
    *,
    trigger_type: str,
    trigger_price: float,
    secondary_row: dict[str, Any] | None,
    market_regime: dict[str, Any] | None = None,
) -> SecondarySignalsSummary | None:
    if not secondary_row:
        return None
    indicators = _evaluate_rules(
        trigger_type=trigger_type.upper(),
        price=float(trigger_price),
        row=secondary_row,
        regime=market_regime,
    )
    return summarize_signals(indicators)
