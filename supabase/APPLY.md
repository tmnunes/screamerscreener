# How to apply Phase 2 migrations

The Supabase project in `.env` (`zgcpreizgafkdfzbrcrp`) is reachable via the
service role REST API, but this machine's Supabase CLI login cannot link/manage
it (access-control). Apply SQL manually once:

1. Open Supabase Dashboard → project matching `SUPABASE_URL`
2. Go to **SQL Editor**
3. Paste the contents of:

   `supabase/migrations/20260823000100_phase2_core_schema.sql`

4. Run the query
5. Confirm tables exist: `market_instruments`, `market_prices_daily`, etc.

Then:

```bash
cd /Users/tiagonunes/Documents/Projects/screamerscreener
source .venv/bin/activate
python -m backend.ingestion.seed_instruments
```
