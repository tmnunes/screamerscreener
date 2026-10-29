"""Strategy protocol and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

SignalFn = Callable[[pd.DataFrame, pd.DataFrame | None], pd.Series]


@dataclass(frozen=True, slots=True)
class StrategySpec:
    id: str
    family: str
    description: str
    timeframe: str
    htf: str | None
    build_signal: SignalFn
    stop_atr_mult: float | None = 2.0
    take_atr_mult: float | None = None
    max_hold_bars: int | None = None
