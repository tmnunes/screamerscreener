-- Phase 2: core schema for ScreamerScreener
-- Daily data + Vortex indicators/triggers; hourly table prepared but unused.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Instruments
-- ---------------------------------------------------------------------------
create table if not exists public.market_instruments (
    id uuid primary key default gen_random_uuid(),
    ticker text not null,
    symbol text not null,
    exchange text not null,
    country text not null,
    name text not null,
    currency text not null,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint market_instruments_ticker_key unique (ticker),
    constraint market_instruments_symbol_key unique (symbol)
);

create index if not exists idx_market_instruments_active
    on public.market_instruments (active);

create index if not exists idx_market_instruments_country
    on public.market_instruments (country);

-- ---------------------------------------------------------------------------
-- Daily OHLCV
-- ---------------------------------------------------------------------------
create table if not exists public.market_prices_daily (
    id uuid primary key default gen_random_uuid(),
    instrument_id uuid not null references public.market_instruments (id) on delete cascade,
    date date not null,
    open numeric not null,
    high numeric not null,
    low numeric not null,
    close numeric not null,
    adjusted_close numeric,
    volume bigint,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint market_prices_daily_instrument_date_key unique (instrument_id, date)
);

create index if not exists idx_market_prices_daily_instrument_id
    on public.market_prices_daily (instrument_id);

create index if not exists idx_market_prices_daily_date
    on public.market_prices_daily (date);

create index if not exists idx_market_prices_daily_instrument_date
    on public.market_prices_daily (instrument_id, date);

-- ---------------------------------------------------------------------------
-- Hourly OHLCV (schema only — no ingestion in v1)
-- ---------------------------------------------------------------------------
create table if not exists public.market_prices_hourly (
    id uuid primary key default gen_random_uuid(),
    instrument_id uuid not null references public.market_instruments (id) on delete cascade,
    timestamp timestamptz not null,
    open numeric not null,
    high numeric not null,
    low numeric not null,
    close numeric not null,
    volume bigint,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint market_prices_hourly_instrument_ts_key unique (instrument_id, timestamp)
);

create index if not exists idx_market_prices_hourly_instrument_id
    on public.market_prices_hourly (instrument_id);

create index if not exists idx_market_prices_hourly_timestamp
    on public.market_prices_hourly (timestamp);

create index if not exists idx_market_prices_hourly_instrument_ts
    on public.market_prices_hourly (instrument_id, timestamp);

-- ---------------------------------------------------------------------------
-- Vortex Bands daily values (parametrized)
-- ---------------------------------------------------------------------------
create table if not exists public.indicator_values_daily (
    id uuid primary key default gen_random_uuid(),
    instrument_id uuid not null references public.market_instruments (id) on delete cascade,
    date date not null,
    basis numeric not null,
    upper numeric not null,
    lower numeric not null,
    length integer not null,
    mult numeric not null,
    source text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint indicator_values_daily_unique
        unique (instrument_id, date, length, mult, source)
);

create index if not exists idx_indicator_values_daily_instrument_date
    on public.indicator_values_daily (instrument_id, date);

create index if not exists idx_indicator_values_daily_params
    on public.indicator_values_daily (length, mult, source);

-- ---------------------------------------------------------------------------
-- Triggers (event-based)
-- ---------------------------------------------------------------------------
create table if not exists public.triggers_daily (
    id uuid primary key default gen_random_uuid(),
    instrument_id uuid not null references public.market_instruments (id) on delete cascade,
    date date not null,
    trigger_type text not null check (trigger_type in ('LONG', 'SHORT', 'STOP')),
    trigger_price numeric not null,
    basis numeric not null,
    upper numeric not null,
    lower numeric not null,
    previous_basis numeric,
    previous_upper numeric,
    previous_lower numeric,
    previous_close numeric,
    length integer not null,
    mult numeric not null,
    source text not null,
    created_at timestamptz not null default now(),
    constraint triggers_daily_unique
        unique (instrument_id, date, trigger_type, length, mult, source)
);

create index if not exists idx_triggers_daily_date
    on public.triggers_daily (date);

create index if not exists idx_triggers_daily_type_date
    on public.triggers_daily (trigger_type, date);

create index if not exists idx_triggers_daily_instrument_date
    on public.triggers_daily (instrument_id, date);

-- ---------------------------------------------------------------------------
-- Trigger forward performance
-- ---------------------------------------------------------------------------
create table if not exists public.trigger_performance (
    id uuid primary key default gen_random_uuid(),
    trigger_id uuid not null references public.triggers_daily (id) on delete cascade,
    return_1d numeric,
    return_3d numeric,
    return_5d numeric,
    return_10d numeric,
    return_20d numeric,
    max_favorable_return numeric,
    max_adverse_return numeric,
    calculated_at timestamptz not null default now(),
    constraint trigger_performance_trigger_id_key unique (trigger_id)
);

create index if not exists idx_trigger_performance_trigger_id
    on public.trigger_performance (trigger_id);

-- ---------------------------------------------------------------------------
-- Pipeline run metadata (ingestion / calculation status)
-- ---------------------------------------------------------------------------
create table if not exists public.pipeline_runs (
    id uuid primary key default gen_random_uuid(),
    run_type text not null check (run_type in ('ingestion', 'calculation', 'refresh')),
    status text not null check (status in ('started', 'success', 'failed')),
    detail jsonb not null default '{}'::jsonb,
    api_requests_used integer not null default 0,
    started_at timestamptz not null default now(),
    finished_at timestamptz
);

create index if not exists idx_pipeline_runs_type_started
    on public.pipeline_runs (run_type, started_at desc);

-- ---------------------------------------------------------------------------
-- updated_at helper
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_market_instruments_updated_at on public.market_instruments;
create trigger trg_market_instruments_updated_at
    before update on public.market_instruments
    for each row execute function public.set_updated_at();

drop trigger if exists trg_market_prices_daily_updated_at on public.market_prices_daily;
create trigger trg_market_prices_daily_updated_at
    before update on public.market_prices_daily
    for each row execute function public.set_updated_at();

drop trigger if exists trg_market_prices_hourly_updated_at on public.market_prices_hourly;
create trigger trg_market_prices_hourly_updated_at
    before update on public.market_prices_hourly
    for each row execute function public.set_updated_at();

drop trigger if exists trg_indicator_values_daily_updated_at on public.indicator_values_daily;
create trigger trg_indicator_values_daily_updated_at
    before update on public.indicator_values_daily
    for each row execute function public.set_updated_at();
