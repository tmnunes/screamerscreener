# How to apply migrations

The Supabase project in `.env` may need SQL applied manually via the Dashboard
SQL Editor if the CLI cannot link the project.

## Order

1. `supabase/migrations/20260823000100_phase2_core_schema.sql`
2. `supabase/migrations/20260823000200_seed_instruments.sql`
3. `supabase/migrations/20260823000300_secondary_indicators.sql` ← secondary indicators
4. `supabase/migrations/20260823000400_return_15d.sql` ← +15d performance column
5. `supabase/migrations/20260823000500_crypto_asset_type.sql` ← STOCK/CRYPTO + crypto regime

## After secondary / 15d / crypto migrations

```bash
source .venv/bin/activate
python -m backend.indicators.calculate_daily --length 47 --mult 1.6 --asset-type STOCK
```

### Crypto bootstrap

```bash
# Set FREECRYPTOAPI_API_KEY in .env first
python -m backend.ingestion.initial_load_crypto
python -m backend.indicators.calculate_daily --asset-type CRYPTO
# or incremental:
python -m backend.ingestion.sync_crypto_data
```

Daily candle dates for crypto use UTC calendar dates as returned by FreeCryptoAPI
`/getOHLC` — crypto is 24/7; missing dates are treated as data gaps, not weekends.

This recalculates Vortex triggers **and** secondary indicators. Secondary values
never create or block LONG / SHORT / STOP. After migration 4, recalculate (or open
triggers) so `return_15d` is filled for LONG stats.

Refresh endpoints are isolated:
- `POST /api/refresh` and `POST /api/refresh/stocks` → EODHD + STOCK only
- `POST /api/refresh/crypto` → FreeCryptoAPI + CRYPTO only


### Optional market regime (SPY / QQQ)

SPY and QQQ are configured as **inactive** instruments. To enable:

1. Set `active=True` for SPY/QQQ in `backend/data/instruments.py` (or update DB)
2. Run seed + sync (uses 2 EODHD requests)
3. Recalculate — fills `market_regime_daily`
