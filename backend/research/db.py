"""Durable research database (SQLite) with incremental candle/funding upserts.

Supabase schema: supabase/migrations/20261029000600_research_futures.sql
SQLite is the local source of truth for research runs when cloud sync is
unavailable; ``sync_to_supabase`` pushes when credentials/network allow.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from backend.research.config import DATA_ROOT

logger = logging.getLogger(__name__)

DB_PATH = DATA_ROOT / "research.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS research_futures_instruments (
    symbol TEXT PRIMARY KEY,
    exchange TEXT NOT NULL DEFAULT 'BINANCE_UM',
    base_asset TEXT NOT NULL,
    quote_asset TEXT NOT NULL DEFAULT 'USDT',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS research_futures_candles (
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    open_time TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL DEFAULT 0,
    quote_volume REAL,
    trades INTEGER,
    taker_buy_base REAL,
    close_time TEXT,
    source TEXT NOT NULL DEFAULT 'binance_vision',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (symbol, interval, open_time)
);

CREATE INDEX IF NOT EXISTS idx_rfc_lookup
    ON research_futures_candles (symbol, interval, open_time);

CREATE TABLE IF NOT EXISTS research_futures_funding (
    symbol TEXT NOT NULL,
    funding_time TEXT NOT NULL,
    funding_rate REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'binance_vision',
    created_at TEXT NOT NULL,
    PRIMARY KEY (symbol, funding_time)
);

CREATE TABLE IF NOT EXISTS research_data_sync_state (
    symbol TEXT NOT NULL,
    data_kind TEXT NOT NULL,
    last_open_time TEXT,
    last_year_month TEXT,
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (symbol, data_kind)
);

CREATE TABLE IF NOT EXISTS research_backtest_runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    period_start TEXT,
    period_end TEXT,
    symbols TEXT NOT NULL,
    cost_taker_fee REAL NOT NULL,
    cost_slippage_bps REAL NOT NULL,
    leverage REAL NOT NULL DEFAULT 1,
    notes TEXT,
    meta TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS research_strategy_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    family TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    params TEXT NOT NULL DEFAULT '{}',
    total_return REAL,
    oos_return REAL,
    max_drawdown REAL,
    sharpe REAL,
    profit_factor REAL,
    win_rate REAL,
    score REAL,
    trades INTEGER NOT NULL DEFAULT 0,
    first_execution_at TEXT,
    last_execution_at TEXT,
    notes TEXT,
    metrics TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE (run_id, strategy_id, symbol),
    FOREIGN KEY (run_id) REFERENCES research_backtest_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rsr_run ON research_strategy_results (run_id);
CREATE INDEX IF NOT EXISTS idx_rsr_score ON research_strategy_results (score DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_db(path: Path | None = None) -> Path:
    db_path = path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    return db_path


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    db_path = ensure_db(path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_instrument(symbol: str, *, conn: sqlite3.Connection | None = None) -> None:
    base = symbol.replace("USDT", "").replace("USD", "") or symbol
    now = _now()

    def _run(c: sqlite3.Connection) -> None:
        c.execute(
            """
            INSERT INTO research_futures_instruments
                (symbol, exchange, base_asset, quote_asset, active, created_at, updated_at)
            VALUES (?, 'BINANCE_UM', ?, 'USDT', 1, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET updated_at=excluded.updated_at, active=1
            """,
            (symbol, base, now, now),
        )

    if conn is not None:
        _run(conn)
    else:
        with connect() as c:
            _run(c)


def upsert_candles(symbol: str, interval: str, df: pd.DataFrame) -> int:
    """Insert-or-replace candles. Returns rows written."""
    if df.empty:
        return 0
    work = df.copy()
    if "timestamp" not in work.columns:
        work["timestamp"] = pd.to_datetime(work["open_time"], unit="ms", utc=True)
    else:
        work["timestamp"] = pd.to_datetime(work["timestamp"], utc=True)
    now = _now()
    rows: list[tuple[Any, ...]] = []
    for r in work.itertuples(index=False):
        ts = getattr(r, "timestamp")
        open_time = pd.Timestamp(ts).isoformat()
        close_time = None
        if hasattr(r, "close_time") and getattr(r, "close_time") == getattr(r, "close_time"):
            try:
                close_time = pd.to_datetime(getattr(r, "close_time"), unit="ms", utc=True).isoformat()
            except Exception:
                close_time = None
        rows.append(
            (
                symbol,
                interval,
                open_time,
                float(getattr(r, "open")),
                float(getattr(r, "high")),
                float(getattr(r, "low")),
                float(getattr(r, "close")),
                float(getattr(r, "volume", 0) or 0),
                float(getattr(r, "quote_volume", 0) or 0)
                if hasattr(r, "quote_volume")
                else None,
                int(getattr(r, "trades", 0) or 0) if hasattr(r, "trades") else None,
                float(getattr(r, "taker_buy_base", 0) or 0)
                if hasattr(r, "taker_buy_base")
                else None,
                close_time,
                "binance_vision",
                now,
                now,
            )
        )
    with connect() as conn:
        upsert_instrument(symbol, conn=conn)
        conn.executemany(
            """
            INSERT INTO research_futures_candles (
                symbol, interval, open_time, open, high, low, close, volume,
                quote_volume, trades, taker_buy_base, close_time, source,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(symbol, interval, open_time) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume,
                quote_volume=excluded.quote_volume, trades=excluded.trades,
                taker_buy_base=excluded.taker_buy_base, close_time=excluded.close_time,
                updated_at=excluded.updated_at
            """,
            rows,
        )
        last = rows[-1][2]
        ym = pd.Timestamp(last).strftime("%Y-%m")
        conn.execute(
            """
            INSERT INTO research_data_sync_state
                (symbol, data_kind, last_open_time, last_year_month, rows_loaded, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, data_kind) DO UPDATE SET
                last_open_time=excluded.last_open_time,
                last_year_month=excluded.last_year_month,
                rows_loaded=excluded.rows_loaded,
                updated_at=excluded.updated_at
            """,
            (symbol, f"klines_{interval}", last, ym, len(rows), now),
        )
    return len(rows)


def upsert_funding(symbol: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    work = df.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], utc=True)
    now = _now()
    rows = [
        (
            symbol,
            pd.Timestamp(r.timestamp).isoformat(),
            float(r.funding_rate),
            "binance_vision",
            now,
        )
        for r in work.itertuples(index=False)
    ]
    with connect() as conn:
        upsert_instrument(symbol, conn=conn)
        conn.executemany(
            """
            INSERT INTO research_futures_funding
                (symbol, funding_time, funding_rate, source, created_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(symbol, funding_time) DO UPDATE SET
                funding_rate=excluded.funding_rate
            """,
            rows,
        )
        last = rows[-1][1]
        conn.execute(
            """
            INSERT INTO research_data_sync_state
                (symbol, data_kind, last_open_time, last_year_month, rows_loaded, updated_at)
            VALUES (?, 'funding', ?, ?, ?, ?)
            ON CONFLICT(symbol, data_kind) DO UPDATE SET
                last_open_time=excluded.last_open_time,
                last_year_month=excluded.last_year_month,
                rows_loaded=excluded.rows_loaded,
                updated_at=excluded.updated_at
            """,
            (symbol, last, pd.Timestamp(last).strftime("%Y-%m"), len(rows), now),
        )
    return len(rows)


def load_candles(symbol: str, interval: str) -> pd.DataFrame:
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT open_time, open, high, low, close, volume, quote_volume, trades,
                   taker_buy_base, close_time
            FROM research_futures_candles
            WHERE symbol=? AND interval=?
            ORDER BY open_time
            """,
            (symbol, interval),
        )
        rows = cur.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["timestamp"] = pd.to_datetime(df["open_time"], utc=True, format="ISO8601")
    df["open_time"] = (df["timestamp"].astype("int64") // 10**6).astype("int64")
    return df


def load_funding(symbol: str) -> pd.DataFrame:
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT funding_time, funding_rate
            FROM research_futures_funding
            WHERE symbol=?
            ORDER BY funding_time
            """,
            (symbol,),
        )
        rows = cur.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["timestamp"] = pd.to_datetime(df["funding_time"], utc=True, format="ISO8601")
    df["funding_time"] = (df["timestamp"].astype("int64") // 10**6).astype("int64")
    return df


def candle_coverage(symbol: str, interval: str) -> dict[str, Any]:
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT COUNT(*) AS n,
                   MIN(open_time) AS start,
                   MAX(open_time) AS end
            FROM research_futures_candles
            WHERE symbol=? AND interval=?
            """,
            (symbol, interval),
        )
        row = cur.fetchone()
    return {"symbol": symbol, "interval": interval, "rows": row["n"], "start": row["start"], "end": row["end"]}


def save_backtest_run(
    *,
    run_id: str,
    symbols: list[str],
    cost_taker_fee: float,
    cost_slippage_bps: float,
    leverage: float,
    period_start: str | None,
    period_end: str | None,
    notes: str = "",
    meta: dict | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO research_backtest_runs (
                id, started_at, finished_at, period_start, period_end, symbols,
                cost_taker_fee, cost_slippage_bps, leverage, notes, meta
            ) VALUES (?,?,NULL,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET notes=excluded.notes, meta=excluded.meta
            """,
            (
                run_id,
                _now(),
                period_start,
                period_end,
                json.dumps(symbols),
                cost_taker_fee,
                cost_slippage_bps,
                leverage,
                notes,
                json.dumps(meta or {}),
            ),
        )


def finish_backtest_run(run_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE research_backtest_runs SET finished_at=? WHERE id=?",
            (_now(), run_id),
        )


def save_strategy_result(run_id: str, row: dict[str, Any]) -> None:
    import uuid

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO research_strategy_results (
                id, run_id, strategy_id, family, symbol, timeframe, params,
                total_return, oos_return, max_drawdown, sharpe, profit_factor,
                win_rate, score, trades, first_execution_at, last_execution_at,
                notes, metrics, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(run_id, strategy_id, symbol) DO UPDATE SET
                total_return=excluded.total_return,
                oos_return=excluded.oos_return,
                max_drawdown=excluded.max_drawdown,
                sharpe=excluded.sharpe,
                profit_factor=excluded.profit_factor,
                win_rate=excluded.win_rate,
                score=excluded.score,
                trades=excluded.trades,
                first_execution_at=excluded.first_execution_at,
                last_execution_at=excluded.last_execution_at,
                notes=excluded.notes,
                metrics=excluded.metrics
            """,
            (
                str(uuid.uuid4()),
                run_id,
                row["strategy_id"],
                row["family"],
                row["symbol"],
                row["timeframe"],
                json.dumps(row.get("params") or {}),
                row.get("total_return"),
                row.get("oos_return"),
                row.get("max_drawdown"),
                row.get("sharpe"),
                row.get("profit_factor"),
                row.get("win_rate"),
                row.get("score"),
                int(row.get("trades") or 0),
                row.get("first_execution_at"),
                row.get("last_execution_at"),
                row.get("notes"),
                json.dumps(row.get("metrics") or {}),
                _now(),
            ),
        )


def sync_to_supabase(symbols: list[str] | None = None) -> dict[str, Any]:
    """Best-effort push of SQLite research data to Supabase REST."""
    try:
        from backend.db import get_supabase
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"import: {exc}"}

    try:
        sb = get_supabase()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

    stats: dict[str, Any] = {"instruments": 0, "candles": 0, "funding": 0, "errors": []}
    with connect() as conn:
        instruments = conn.execute("SELECT * FROM research_futures_instruments").fetchall()
        for inst in instruments:
            if symbols and inst["symbol"] not in symbols:
                continue
            try:
                sb.table("research_futures_instruments").upsert(
                    {
                        "symbol": inst["symbol"],
                        "exchange": inst["exchange"],
                        "base_asset": inst["base_asset"],
                        "quote_asset": inst["quote_asset"],
                        "active": bool(inst["active"]),
                    },
                    on_conflict="symbol",
                ).execute()
                stats["instruments"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["errors"].append(str(exc))
                return {**stats, "ok": False}

            # Candles in chunks
            cur = conn.execute(
                """
                SELECT symbol, interval, open_time, open, high, low, close, volume,
                       quote_volume, trades, taker_buy_base, close_time, source
                FROM research_futures_candles WHERE symbol=?
                ORDER BY interval, open_time
                """,
                (inst["symbol"],),
            )
            batch: list[dict] = []
            while True:
                row = cur.fetchone()
                if row is None:
                    break
                batch.append(
                    {
                        "symbol": row["symbol"],
                        "interval": row["interval"],
                        "open_time": row["open_time"],
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row["volume"],
                        "quote_volume": row["quote_volume"],
                        "trades": row["trades"],
                        "taker_buy_base": row["taker_buy_base"],
                        "close_time": row["close_time"],
                        "source": row["source"],
                    }
                )
                if len(batch) >= 500:
                    try:
                        sb.table("research_futures_candles").upsert(
                            batch, on_conflict="symbol,interval,open_time"
                        ).execute()
                        stats["candles"] += len(batch)
                    except Exception as exc:  # noqa: BLE001
                        stats["errors"].append(str(exc))
                        return {**stats, "ok": False}
                    batch = []
            if batch:
                sb.table("research_futures_candles").upsert(
                    batch, on_conflict="symbol,interval,open_time"
                ).execute()
                stats["candles"] += len(batch)

            fcur = conn.execute(
                "SELECT symbol, funding_time, funding_rate, source FROM research_futures_funding WHERE symbol=?",
                (inst["symbol"],),
            )
            fbatch: list[dict] = []
            for row in fcur.fetchall():
                fbatch.append(dict(row))
                if len(fbatch) >= 500:
                    sb.table("research_futures_funding").upsert(
                        fbatch, on_conflict="symbol,funding_time"
                    ).execute()
                    stats["funding"] += len(fbatch)
                    fbatch = []
            if fbatch:
                sb.table("research_futures_funding").upsert(
                    fbatch, on_conflict="symbol,funding_time"
                ).execute()
                stats["funding"] += len(fbatch)

    stats["ok"] = True
    return stats
