# How to apply migrations

The Supabase project in `.env` may need SQL applied manually via the Dashboard
SQL Editor if the CLI cannot link the project.

## Order

1. `supabase/migrations/20260823000100_phase2_core_schema.sql`
2. `supabase/migrations/20260823000200_seed_instruments.sql`
3. `supabase/migrations/20260823000300_secondary_indicators.sql` ← secondary indicators
4. `supabase/migrations/20260823000400_return_15d.sql` ← +15d performance column

## After secondary / 15d migrations

```bash
source .venv/bin/activate
python -m backend.indicators.calculate_daily --length 47 --mult 1.6
```

This recalculates Vortex triggers **and** secondary indicators. Secondary values
never create or block LONG / SHORT / STOP. After migration 4, recalculate (or open
triggers) so `return_15d` is filled for LONG stats.

### Optional market regime (SPY / QQQ)

SPY and QQQ are configured as **inactive** instruments. To enable:

1. Set `active=True` for SPY/QQQ in `backend/data/instruments.py` (or update DB)
2. Run seed + sync (uses 2 EODHD requests)
3. Recalculate — fills `market_regime_daily`
