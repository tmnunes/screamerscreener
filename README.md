# ScreamerScreener

Stock screening and research web app based on the TradingView **Vortex Bands** indicator.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | Python, FastAPI |
| Database | Supabase PostgreSQL |
| Market data | EODHD API (backend only) |
| Charts | TradingView Lightweight Charts (Phase 15) |

## Architecture

```
EODHD
  ↓
Python Data Ingestion
  ↓
Supabase PostgreSQL
  ↓
Indicator Engine → Trigger Engine → Performance Engine
  ↓
FastAPI
  ↓
Next.js Web App
```

The frontend never calls EODHD. API keys stay in backend environment variables only.

## Project structure

```
screamerscreener/
├── frontend/          # Next.js web app
├── backend/           # FastAPI + ingestion + indicators
│   ├── api/
│   ├── data/
│   ├── indicators/
│   ├── signals/
│   ├── backtest/
│   └── ingestion/
├── supabase/
│   └── migrations/
├── tests/
├── .env.example
└── README.md
```

## Setup (Phase 1)

### Prerequisites

- Node.js 20+ (tested with 22)
- Python 3.11+ (tested with 3.13)
- EODHD API key (free tier)
- Supabase project (Phase 2+)

### 1. Environment

```bash
cp .env.example .env
# Edit .env and set EODHD_API_KEY (and later Supabase keys)
```

### 2. Backend

```bash
cd /Users/tiagonunes/Documents/Projects/screamerscreener
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Backend API (smoke check)

```bash
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

Health check: http://localhost:8000/api/health

## Implementation phases

We implement **one phase at a time**. Do not skip ahead.

| Phase | Status | Description |
|------:|--------|-------------|
| 1 | **Current** | Project setup |
| 2 | Pending | Supabase migrations |
| 3 | Pending | Instrument configuration |
| 4 | Pending | EODHD provider |
| 5 | Pending | Initial historical daily ingestion |
| 6 | Pending | Validate database data |
| 7 | Pending | Vortex calculation |
| 8 | Pending | Trigger engine |
| 9 | Pending | Unit tests |
| 10 | Pending | PineScript / Python validation |
| 11 | Pending | Performance calculations |
| 12 | Pending | FastAPI endpoints |
| 13 | Pending | Next.js dashboard |
| 14 | Pending | Last 7 days |
| 15 | Pending | Stock detail |
| 16 | Pending | Trigger detail |
| 17 | Pending | Data status |
| 18 | Pending | Manual refresh |
| 19 | Later | Secondary indicators |
| 20 | Later | Parameter optimization |

## Defaults (from Phase 7+)

- Timeframe: Daily (1D)
- Vortex Length: 47
- Vortex Multiplier: 1.6
- Source: HLC3

## Security

Never commit `.env`. Never put `EODHD_API_KEY` or `SUPABASE_SERVICE_ROLE_KEY` in the frontend.
