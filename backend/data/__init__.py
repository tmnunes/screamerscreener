"""Market data providers and abstractions.

Timeframe support (architecture only in early phases):
- DAILY  — used by Vortex Bands in v1
- HOURLY — reserved for later (no downloads in Phase 1–18)
"""

from enum import Enum


class Timeframe(str, Enum):
    DAILY = "DAILY"
    HOURLY = "HOURLY"
