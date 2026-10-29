# Crypto Perpetual Futures — Research Report (updated)

## Data storage (DB)

Market data for research is persisted in SQLite:

- Path: `data/research/research.db`
- Tables: candles (`5m/15m/30m/1h`), funding, sync watermarks, backtest runs/results
- Incremental upserts by `(symbol, interval, open_time)` — monthly extensions only insert new bars
- Supabase mirror schema: `supabase/migrations/20261029000600_research_futures.sql`
- Load: `python -m backend.research.runner --ingest-db`
- Sync cloud (after applying migration): `python -m backend.research.runner --sync-supabase`

| Symbol | 5m bars | Start | End |
|--------|--------:|-------|-----|
| BTCUSDT | 210,240 | 2024-10-01 | 2026-09-30 |
| ETHUSDT | 210,240 | 2024-10-01 | 2026-09-30 |

## Cost model

Taker 4 bps/side + 1.5 bps slippage + historical funding · leverage 1x.

## Optimization

268 parameterised strategies × BTCUSDT + ETHUSDT = **536 evaluations**.  
**41** strategies with **positive mean net return across both symbols**.  
**85** symbol-level positive results.

### A) Positive on **both** BTC and ETH (strict)

Only **funding-fade** variants cleared this bar under baseline costs:

| Strategy | BTC | ETH | Mean | Trades (avg) | First execution | Last execution | Mean DD |
|----------|----:|----:|-----:|-------------:|-----------------|----------------|--------:|
| `FUND_h0.0005_l-0.0002_hold48_1h` | **+3.4%** | **+29.1%** | **+16.3%** | 3.5 | 2024-11-12 09:00 UTC | 2026-04-21 18:00 UTC | **-6.4%** |
| `FUND_h0.0005_l-0.0002_hold24_1h` | **+4.4%** | **+22.7%** | **+13.5%** | 3.5 | 2024-11-12 09:00 UTC | 2026-04-20 18:00 UTC | -4.1% |
| `FUND_h0.0003_l-0.0002_hold12_1h` | **+3.2%** | **+18.9%** | **+11.0%** | 14.5 | 2024-11-11 02:00 UTC | 2026-04-20 06:00 UTC | -5.9% |

Rule: short when funding ≥ +0.05% (or +0.03%), long when ≤ −0.02%; hold N hours on 1h bars.

### B) Highest mean return (ETH-driven; BTC often negative)

| Strategy | Mean ret | ETH | BTC | Trades | First → Last |
|----------|---------:|----:|----:|-------:|--------------|
| `EMAADX_12_50_a30_s2.5_t4.0_1h` | **+112%** | +239% | −15% | ~511 | 2024-10-06 → 2026-09-24 |
| `KELT_20x2.5_1h` | **+83%** | +200% | −35% | ~485 | 2024-10-01 → 2026-09-30 |

Rule (EMAADX): 1h EMA12/50 + ADX≥30 + stop 2.5×ATR + take 4×ATR.

## Caveats

- **Strict dual-asset winners** exist but have **few trades** (funding extremes are rare) — good risk profile, thin statistics.
- High headline returns are mostly **ETH**; do not treat mean(+112%) as BTC-ready without a BTC-specific filter.
- Top trend/breakout systems still show **~40–55% DD** and fragile OOS.

## Frequency-aware rerun (incl. 5m)

Constraint: **≥52 trades/symbol** over ~2y (≈ ≥1 trade / 2 weeks).  
Grid: 176 specs × 2 symbols (5m+15m+1h).

### Best pick now

**`KELT_20x3.0_s2.5_t4.0_1h`** (Keltner breakout 1h)

| | BTC | ETH | Mean |
|--|----:|----:|-----:|
| Net return | **+5.7%** | **+478.8%** | **+242%** |
| OOS | +8.8% | +12.0% | **+10.4%** |
| Max DD | -34% | -30% | -32% |
| Trades | 392 | 399 | ~396 (≈ 3.8 / week) |
| First → last | 2024-10-01 21:00 UTC → 2026-09-30 20:00 UTC | | |

Rule: 1h Keltner(20, mult=3.0) breakout; stop 2.5×ATR; take 4×ATR.

More balanced BTC/ETH: **`DON_80_10_s3.0_t4.0_1h`** — BTC **+58%**, ETH **+164%**, ~405 trades, DD ~−46%.

### 5m

5m **was tested** in this freq pass (112 symbol-evals). **No net-positive 5m** under taker costs; best MR ≈ **−29%** with ~260–320 trades.

## Reproduce

```bash
python -m backend.research.runner --ingest-db --symbols BTCUSDT ETHUSDT
python -m backend.research.runner --optimize-freq --symbols BTCUSDT ETHUSDT --min-trades 52
```

Artifacts: `optimize_consensus_freq.csv`, `optimize_both_positive_freq.csv`, SQLite `research_strategy_results`.
