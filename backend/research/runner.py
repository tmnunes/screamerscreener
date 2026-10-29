"""CLI: download → validate → backtest → rank crypto perpetual strategies.

Usage:
  python -m backend.research.runner --download
  python -m backend.research.runner --run
  python -m backend.research.runner --download --run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from backend.research.config import (
    PRIMARY_SYMBOLS,
    REPORTS_DIR,
    ResearchUniverse,
    CostModel,
)
from backend.research.data.download import latest_complete_month
from backend.research.data.store import (
    build_symbol_datasets,
    load_dataset,
    load_funding_normalized,
)
from backend.research.ranking import (
    RankedResult,
    cross_symbol_consensus,
    evaluate_strategy,
    results_to_frame,
)
from backend.research.strategies.catalog import build_catalog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("research.runner")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Crypto quant research runner")
    p.add_argument("--download", action="store_true", help="Download/normalize data")
    p.add_argument(
        "--ingest-db",
        action="store_true",
        help="Load existing parquet/raw normalized data into research SQLite DB",
    )
    p.add_argument("--run", action="store_true", help="Run strategy backtests + ranking")
    p.add_argument(
        "--optimize",
        action="store_true",
        help="Large parameter search aiming for net-positive strategies",
    )
    p.add_argument(
        "--optimize-freq",
        action="store_true",
        help="Frequency-aware search (incl. 5m); require ~≥1 trade / 1–2 weeks",
    )
    p.add_argument(
        "--sync-supabase",
        action="store_true",
        help="Push research SQLite data to Supabase (requires migration applied)",
    )
    p.add_argument(
        "--symbols",
        nargs="+",
        default=list(PRIMARY_SYMBOLS),
        help="Symbols to research (default BTCUSDT ETHUSDT)",
    )
    p.add_argument("--start", default="2024-10-01", help="YYYY-MM-DD start month")
    p.add_argument("--force", action="store_true", help="Redownload raw archives")
    p.add_argument("--quick", action="store_true", help="BTCUSDT only, fewer strategies")
    p.add_argument(
        "--max-trials",
        type=int,
        default=None,
        help="Cap optimize trials (per symbol) for smoke tests",
    )
    p.add_argument(
        "--min-trades",
        type=int,
        default=52,
        help="Min trades per symbol over the sample (~52 ≈ 1 per 2 weeks in 2y)",
    )
    return p.parse_args(argv)


def _start_date(text: str) -> date:
    y, m, d = text.split("-")
    return date(int(y), int(m), int(d))


def cmd_ingest_db(symbols: list[str]) -> None:
    """Persist parquet datasets into SQLite research DB (incremental upserts)."""
    from backend.research import db as research_db
    from backend.research.config import NORMALIZED_DIR

    research_db.ensure_db()
    for symbol in symbols:
        for interval in ("5m", "15m", "30m", "1h"):
            path = NORMALIZED_DIR / symbol / f"{interval}.parquet"
            if not path.exists():
                logger.warning("Missing parquet %s", path)
                continue
            df = pd.read_parquet(path)
            n = research_db.upsert_candles(symbol, interval, df)
            logger.info("DB %s %s upserted=%s", symbol, interval, n)
        fpath = NORMALIZED_DIR / symbol / "funding.parquet"
        if fpath.exists():
            n = research_db.upsert_funding(symbol, pd.read_parquet(fpath))
            logger.info("DB %s funding upserted=%s", symbol, n)
        logger.info("Coverage %s", research_db.candle_coverage(symbol, "5m"))


def cmd_optimize(
    symbols: list[str],
    max_trials: int | None = None,
    *,
    space: str = "default",
    min_trades: int = 52,
) -> pd.DataFrame:
    from backend.research.optimize import run_optimization
    from pathlib import Path

    frames_by_symbol: dict[str, dict[str, pd.DataFrame]] = {}
    funding_by_symbol: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        frames: dict[str, pd.DataFrame] = {}
        for tf in ("5m", "15m", "30m", "1h"):
            df, meta = load_dataset(symbol, tf)
            if df.empty:
                logger.warning("Missing %s %s — run --ingest-db or --download", symbol, tf)
                continue
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            frames[tf] = df
            if tf == "5m" and meta:
                logger.info(
                    "Loaded %s 5m from %s: %s → %s (%s bars)",
                    symbol,
                    meta.source,
                    meta.start,
                    meta.end,
                    meta.rows,
                )
        funding = load_funding_normalized(symbol)
        if not funding.empty:
            funding["timestamp"] = pd.to_datetime(funding["timestamp"], utc=True)
        frames_by_symbol[symbol] = frames
        funding_by_symbol[symbol] = funding

    consensus = run_optimization(
        symbols,
        frames_by_symbol,
        funding_by_symbol,
        cost=CostModel(),
        max_trials=max_trials,
        space=space,
        min_trades=min_trades,
    )
    if consensus.empty:
        logger.error("Optimize produced no rows (or none passed min_trades=%s)", min_trades)
        return consensus

    pos = consensus[consensus["mean_return"] > 0]
    logger.info(
        "Strategies with positive mean net return (min_trades>=%s): %s",
        min_trades,
        len(pos),
    )
    cols = [
        c
        for c in [
            "strategy_id",
            "family",
            "timeframe",
            "mean_return",
            "mean_oos",
            "mean_dd",
            "mean_trades",
            "min_trades",
            "first_execution_at",
            "last_execution_at",
            "symbols",
        ]
        if c in consensus.columns
    ]
    print(f"\n=== TOP BY MEAN NET RETURN (min_trades>={min_trades}) ===")
    print(consensus[cols].head(20).to_string(index=False))
    if not pos.empty:
        print("\n=== NET POSITIVE (mean across symbols) ===")
        print(pos[cols].head(20).to_string(index=False))
    both_path = REPORTS_DIR / (
        f"optimize_both_positive_{space}.csv"
        if space != "default"
        else "optimize_both_positive.csv"
    )
    if both_path.exists():
        both = pd.read_csv(both_path)
        print("\n=== BOTH BTC+ETH POSITIVE + FREQUENCY ===")
        print(both.head(20).to_string(index=False))
    return consensus


def cmd_download(symbols: list[str], start: date, force: bool) -> dict:
    end = latest_complete_month()
    logger.info(
        "Downloading Binance UM futures 5m (+funding) %s → %s for %s",
        start,
        end,
        symbols,
    )
    all_reports = {}
    for symbol in symbols:
        logger.info("Building datasets for %s", symbol)
        reports = build_symbol_datasets(symbol, start=start, end=end, force=force)
        all_reports[symbol] = {k: v.as_dict() for k, v in reports.items()}
        for interval, q in reports.items():
            logger.info(
                "%s %s rows=%s start=%s end=%s missing=%s gap_ratio=%s ok=%s",
                symbol,
                interval,
                q.rows,
                q.start,
                q.end,
                q.missing_candles,
                q.gap_ratio,
                q.ok,
            )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "data_quality.json"
    path.write_text(json.dumps(all_reports, indent=2))
    logger.info("Wrote %s", path)
    return all_reports


def cmd_run(symbols: list[str], quick: bool = False) -> pd.DataFrame:
    catalog = build_catalog()
    if quick:
        keep = {
            "A2_ema_adx_15m",
            "A4_ema_triple_1h",
            "B3_rsi_macd_15m",
            "C1_donchian55_1h",
            "D1_bb_rsi_mr_15m",
            "E1_1h_ema_15m_rsi",
            "E3_1h_trend_15m_don",
            "F1_trend_mom_1h",
            "F2_squeeze_htf_15m",
        }
        catalog = [s for s in catalog if s.id in keep]

    cost = CostModel()
    rows: list[RankedResult] = []
    period_meta: dict[str, dict] = {}

    for symbol in symbols:
        frames: dict[str, pd.DataFrame] = {}
        for tf in ("5m", "15m", "30m", "1h"):
            df, meta = load_dataset(symbol, tf)
            if df.empty:
                logger.warning("Missing dataset %s %s — run --download first", symbol, tf)
                continue
            if "timestamp" not in df.columns:
                df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
            else:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            frames[tf] = df
            if tf == "5m" and meta:
                period_meta[symbol] = {
                    "start": meta.start,
                    "end": meta.end,
                    "rows": meta.rows,
                    "quality_ok": meta.quality.get("ok")
                    if isinstance(meta.quality, dict)
                    else None,
                }
        funding = load_funding_normalized(symbol)
        if not funding.empty:
            funding["timestamp"] = pd.to_datetime(funding["timestamp"], utc=True)

        if "5m" not in frames:
            continue

        for spec in catalog:
            logger.info("Evaluating %s on %s (%s)", spec.id, symbol, spec.timeframe)
            try:
                result = evaluate_strategy(spec, symbol, frames, funding, cost=cost)
            except Exception:
                logger.exception("Strategy failed: %s %s", spec.id, symbol)
                continue
            if result is not None:
                rows.append(result)
                logger.info(
                    "  score=%.3f full_ret=%.2f%% oos_ret=%.2f%% dd=%.2f%% trades=%s notes=%s",
                    result.score,
                    100 * result.metrics_full.get("total_return", 0),
                    100 * result.metrics_oos.get("total_return", 0),
                    100 * result.metrics_full.get("max_drawdown", 0),
                    int(result.metrics_full.get("trades", 0)),
                    result.notes,
                )

    ranked = results_to_frame(rows)
    consensus = cross_symbol_consensus(ranked)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ranked_path = REPORTS_DIR / "strategy_ranking.csv"
    consensus_path = REPORTS_DIR / "strategy_consensus.csv"
    summary_path = REPORTS_DIR / "summary.json"
    ranked.to_csv(ranked_path, index=False)
    consensus.to_csv(consensus_path, index=False)

    top = consensus.head(10).to_dict(orient="records") if not consensus.empty else []
    summary = {
        "period_by_symbol": period_meta,
        "cost_model": {
            "taker_fee": cost.taker_fee,
            "slippage_bps": cost.slippage_bps,
            "leverage": 1.0,
        },
        "n_evaluations": len(rows),
        "top_consensus": top,
        "evidence_note": (
            "Returns are net of configured taker fees, slippage, and historical "
            "funding. Walk-forward: 70% IS / 30% OOS. Leverage fixed at 1x."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2, default=str))
    logger.info("Wrote %s", ranked_path)
    logger.info("Wrote %s", consensus_path)
    logger.info("Wrote %s", summary_path)
    _write_markdown_report(summary, consensus, ranked)
    return consensus


def _write_markdown_report(
    summary: dict,
    consensus: pd.DataFrame,
    ranked: pd.DataFrame,
) -> None:
    lines = [
        "# Crypto Perpetual Futures — Strategy Research Report",
        "",
        "## Data period (actually retrieved)",
        "",
    ]
    for sym, meta in summary.get("period_by_symbol", {}).items():
        lines.append(
            f"- **{sym}**: `{meta.get('start')}` → `{meta.get('end')}` "
            f"({meta.get('rows')}×5m bars)"
        )
    cost = summary.get("cost_model", {})
    lines += [
        "",
        "## Cost model",
        "",
        f"- Taker fee: {cost.get('taker_fee')}",
        f"- Slippage: {cost.get('slippage_bps')} bps/side",
        f"- Leverage: {cost.get('leverage')}x",
        f"- Funding: historical Binance UM funding rates applied at event timestamps",
        "",
        "## Ranking method",
        "",
        summary.get("evidence_note", ""),
        "",
        "## Top strategies (cross-symbol consensus)",
        "",
    ]
    if consensus.empty:
        lines.append("_No results._")
    else:
        lines.append(
            "| Rank | Strategy | Family | TF | Mean score | Mean return | Mean OOS | Mean DD | Sharpe |"
        )
        lines.append("|---:|---|---|---|---:|---:|---:|---:|---:|")
        for i, row in consensus.head(15).iterrows():
            lines.append(
                "| {rank} | `{sid}` | {fam} | {tf} | {sc:.3f} | {ret:.1%} | {oos:.1%} | {dd:.1%} | {sh:.2f} |".format(
                    rank=i + 1,
                    sid=row["strategy_id"],
                    fam=row["family"],
                    tf=row["timeframe"],
                    sc=row["mean_score"],
                    ret=row["mean_full_return"],
                    oos=row["mean_oos_return"],
                    dd=row["mean_max_dd"],
                    sh=row["mean_sharpe"],
                )
            )
    lines += ["", "## Per-symbol detail (top 10 rows)", "", "```"]
    if not ranked.empty:
        show = ranked.head(10)[
            [
                c
                for c in [
                    "strategy_id",
                    "symbol",
                    "score",
                    "full_total_return",
                    "oos_total_return",
                    "full_max_drawdown",
                    "full_sharpe",
                    "full_trades",
                    "notes",
                ]
                if c in ranked.columns
            ]
        ]
        lines.append(show.to_string(index=False))
    lines.append("```")
    path = REPORTS_DIR / "REPORT.md"
    path.write_text("\n".join(lines) + "\n")
    logger.info("Wrote %s", path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not any(
        [
            args.download,
            args.run,
            args.optimize,
            args.optimize_freq,
            args.ingest_db,
            args.sync_supabase,
        ]
    ):
        args.ingest_db = True
        args.optimize_freq = True
    symbols = list(PRIMARY_SYMBOLS) if args.quick else args.symbols
    if args.quick:
        symbols = ["BTCUSDT"]
    start = _start_date(args.start)
    if args.download:
        cmd_download(symbols, start, args.force)
    if args.ingest_db:
        cmd_ingest_db(symbols)
    if args.optimize or args.optimize_freq:
        space = "freq" if args.optimize_freq else "default"
        consensus = cmd_optimize(
            symbols,
            max_trials=args.max_trials,
            space=space,
            min_trades=args.min_trades,
        )
        if consensus.empty:
            return 1
    if args.run:
        consensus = cmd_run(symbols, quick=args.quick)
        if consensus.empty:
            logger.error("No ranking results produced")
            return 1
        print("\n=== TOP CONSENSUS ===")
        cols = [
            c
            for c in [
                "strategy_id",
                "family",
                "timeframe",
                "mean_full_return",
                "mean_oos_return",
                "mean_max_dd",
                "mean_trades",
                "first_execution_at",
                "last_execution_at",
                "mean_score",
            ]
            if c in consensus.columns
        ]
        print(consensus[cols].head(10).to_string(index=False))
    if args.sync_supabase:
        from backend.research import db as research_db

        stats = research_db.sync_to_supabase(symbols)
        logger.info("Supabase sync: %s", stats)
        if not stats.get("ok"):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
