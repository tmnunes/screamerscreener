"""Vortex Bands trigger detection (event-based, no look-ahead)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TriggerType(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    STOP = "STOP"


class PositionState(str, Enum):
    FLAT = "FLAT"
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True, slots=True)
class TriggerEvent:
    index: int
    trigger_type: TriggerType
    trigger_price: float
    basis: float
    upper: float
    lower: float
    previous_basis: float
    previous_upper: float
    previous_lower: float
    previous_close: float


def detect_triggers(
    closes: list[float],
    basis: list[float],
    upper: list[float],
    lower: list[float],
) -> list[TriggerEvent]:
    """Detect LONG / SHORT / STOP crossings using only bars <= t."""
    n = len(closes)
    if not (len(basis) == len(upper) == len(lower) == n):
        raise ValueError("series lengths must match")
    if n < 2:
        return []

    events: list[TriggerEvent] = []
    for t in range(1, n):
        prev = t - 1
        common = dict(
            index=t,
            trigger_price=closes[t],
            basis=basis[t],
            upper=upper[t],
            lower=lower[t],
            previous_basis=basis[prev],
            previous_upper=upper[prev],
            previous_lower=lower[prev],
            previous_close=closes[prev],
        )

        # LONG: blue/upper crosses above orange/lower
        if upper[prev] <= lower[prev] and upper[t] > lower[t]:
            events.append(TriggerEvent(trigger_type=TriggerType.LONG, **common))

        # SHORT: orange/lower crosses above blue/upper
        if lower[prev] <= upper[prev] and lower[t] > upper[t]:
            events.append(TriggerEvent(trigger_type=TriggerType.SHORT, **common))

        # STOP: close crosses below basis
        if closes[prev] >= basis[prev] and closes[t] < basis[t]:
            events.append(TriggerEvent(trigger_type=TriggerType.STOP, **common))

    return events


def apply_state_machine(events: list[TriggerEvent]) -> list[tuple[TriggerEvent, PositionState]]:
    """Return each event with the position state *after* applying it."""
    state = PositionState.FLAT
    out: list[tuple[TriggerEvent, PositionState]] = []

    for event in events:
        if event.trigger_type == TriggerType.LONG:
            state = PositionState.LONG
        elif event.trigger_type == TriggerType.SHORT:
            state = PositionState.SHORT
        elif event.trigger_type == TriggerType.STOP:
            if state in {PositionState.LONG, PositionState.SHORT}:
                state = PositionState.FLAT
        out.append((event, state))

    return out
