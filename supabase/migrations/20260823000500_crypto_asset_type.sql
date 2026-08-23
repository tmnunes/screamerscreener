-- Crypto universe support: asset_type + crypto metadata + crypto market regime.
-- Does not alter existing STOCK rows (default asset_type = STOCK).

-- ---------------------------------------------------------------------------
-- Instruments: STOCK | CRYPTO
-- ---------------------------------------------------------------------------
alter table public.market_instruments
    add column if not exists asset_type text not null default 'STOCK';

alter table public.market_instruments
    drop constraint if exists market_instruments_asset_type_check;

alter table public.market_instruments
    add constraint market_instruments_asset_type_check
        check (asset_type in ('STOCK', 'CRYPTO'));

alter table public.market_instruments
    add column if not exists api_symbol text;

alter table public.market_instruments
    add column if not exists crypto_rank integer;

alter table public.market_instruments
    add column if not exists market_cap numeric;

alter table public.market_instruments
    add column if not exists in_top_universe boolean not null default true;

create index if not exists idx_market_instruments_asset_type
    on public.market_instruments (asset_type);

create index if not exists idx_market_instruments_asset_active
    on public.market_instruments (asset_type, active);

-- Backfill stocks
update public.market_instruments
set asset_type = 'STOCK'
where asset_type is null or asset_type = '';

-- ---------------------------------------------------------------------------
-- Pipeline run types (stocks + crypto isolation)
-- ---------------------------------------------------------------------------
alter table public.pipeline_runs
    drop constraint if exists pipeline_runs_run_type_check;

alter table public.pipeline_runs
    add constraint pipeline_runs_run_type_check
        check (run_type in (
            'ingestion',
            'calculation',
            'refresh',
            'ingestion_crypto',
            'calculation_crypto',
            'refresh_crypto'
        ));

-- ---------------------------------------------------------------------------
-- Crypto market regime (BTC benchmark — independent of SPY/QQQ)
-- ---------------------------------------------------------------------------
create table if not exists public.crypto_market_regime_daily (
    id uuid primary key default gen_random_uuid(),
    date date not null unique,
    btc_close numeric,
    btc_sma50 numeric,
    btc_sma200 numeric,
    btc_above_sma50 boolean,
    btc_above_sma200 boolean,
    btc_rsi14 numeric,
    btc_trend text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_crypto_market_regime_daily_updated_at
    on public.crypto_market_regime_daily;
create trigger trg_crypto_market_regime_daily_updated_at
    before update on public.crypto_market_regime_daily
    for each row execute function public.set_updated_at();
