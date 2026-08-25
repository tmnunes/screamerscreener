# ScreamerScreener

Stock screening and research based on TradingView **Vortex Bands**.

## Stack

- Frontend: Next.js + TypeScript + Tailwind
- Backend: Python FastAPI
- DB: Supabase PostgreSQL
- Market data: EODHD (backend only)

## Quick start

### 1. Environment

```bash
cp .env.example .env
```

Fill at least:

- `EODHD_API_KEY` (**required** for ingestion — currently empty in your `.env`)
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `API_URL=http://localhost:8000` (Next.js server → FastAPI; not exposed to the browser)


Frontend public env:

```bash
cp frontend/.env.example frontend/.env.local
# set API_URL=http://localhost:8000
```

### 2. Apply database migrations (Phase 2–3)

Supabase CLI cannot link this project from the current login. Apply SQL manually:

1. Supabase Dashboard → SQL Editor
2. Run `supabase/migrations/20260823000100_phase2_core_schema.sql`
3. Run `supabase/migrations/20260823000200_seed_instruments.sql`

Details: `supabase/APPLY.md`

### 3. Backend

```bash
cd /Users/tiagonunes/Documents/Projects/screamerscreener
python3 -m venv .venv   # if needed
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Ingest + calculate (uses EODHD quota)

```bash
# Optional: verify PT/US symbols (2 API requests)
python -m backend.ingestion.verify_symbols

# ~15 API requests — one year daily history
python -m backend.ingestion.initial_load

# Validate stored OHLC
python -m backend.ingestion.validate_data

# Vortex + triggers + performance
python -m backend.indicators.calculate_daily --length 47 --mult 1.6

# Export CSV for TradingView comparison
python -m backend.tools.export_vortex_csv --ticker AAPL
```

Later days (incremental):

```bash
python -m backend.ingestion.sync_market_data
python -m backend.indicators.calculate_daily
```

### 5. Run apps

```bash
# API
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

Open http://localhost:3000/dashboard

## Vortex defaults

| Param | Value |
|-------|-------|
| Length | 47 |
| Multiplier | 1.6 |
| Source | hlc3 |
| Timeframe | 1D |

## Tests

```bash
source .venv/bin/activate
pytest
```

## Architecture status

| Phase | Status |
|------:|--------|
| 1 Project setup | Done |
| 2 Migrations | SQL ready — apply in dashboard |
| 3 Instruments | Done (config + seed SQL) |
| 4 EODHD provider | Done |
| 5 Ingestion | Done |
| 6 Validation | Done |
| 7 Vortex math | Done |
| 8 Triggers | Done |
| 9 Unit tests | Done |
| 10 TV CSV export | Done |
| 11 Performance | Done |
| 12 FastAPI | Done |
| 13–18 Dashboard UI | Done (MVP) |
| 19 Secondary indicators | Not started |
| 20 Optimization | Not started |

## Security

Never expose `EODHD_API_KEY` or `SUPABASE_SERVICE_ROLE_KEY` to the browser.
