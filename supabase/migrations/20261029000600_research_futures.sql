-- Quant research: Binance USD-M perpetual futures candles, funding, and backtest results.
-- Apply in Supabase SQL Editor after prior migrations (see supabase/APPLY.md).

-- ---------------------------------------------------------------------------
-- Research instruments (perp symbols; separate from screener spot universe)
-- ---------------------------------------------------------------------------
create table if not exists public.research_futures_instruments (
    id uuid primary key default gen_random_uuid(),
    symbol text not null,
    exchange text not null default 'BINANCE_UM',
    base_asset text not null,
    quote_asset text not null default 'USDT',
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint research_futures_instruments_symbol_key unique (symbol)
);

-- ---------------------------------------------------------------------------
-- Intraday / HTF OHLCV (native 5m + aggregates). Incremental by open_time.
-- ---------------------------------------------------------------------------
create table if not exists public.research_futures_candles (
    id bigserial primary key,
    symbol text not null references public.research_futures_instruments (symbol) on delete cascade,
    interval text not null,
    open_time timestamptz not null,
    open numeric not null,
    high numeric not null,
    low numeric not null,
    close numeric not null,
    volume numeric not null default 0,
    quote_volume numeric,
    trades integer,
    taker_buy_base numeric,
    close_time timestamptz,
    source text not null default 'binance_vision',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint research_futures_candles_unique unique (symbol, interval, open_time),
    constraint research_futures_candles_interval_chk
        check (interval in ('5m', '15m', '30m', '1h', '4h', '1d'))
);

create index if not exists idx_research_futures_candles_lookup
    on public.research_futures_candles (symbol, interval, open_time);

create index if not exists idx_research_futures_candles_open_time
    on public.research_futures_candles (open_time);

-- ---------------------------------------------------------------------------
-- Historical funding rates
-- ---------------------------------------------------------------------------
create table if not exists public.research_futures_funding (
    id bigserial primary key,
    symbol text not null references public.research_futures_instruments (symbol) on delete cascade,
    funding_time timestamptz not null,
    funding_rate numeric not null,
    source text not null default 'binance_vision',
    created_at timestamptz not null default now(),
    constraint research_futures_funding_unique unique (symbol, funding_time)
);

create index if not exists idx_research_futures_funding_lookup
    on public.research_futures_funding (symbol, funding_time);

-- ---------------------------------------------------------------------------
-- Sync watermark for monthly incremental loads
-- ---------------------------------------------------------------------------
create table if not exists public.research_data_sync_state (
    id uuid primary key default gen_random_uuid(),
    symbol text not null,
    data_kind text not null, -- 'klines_5m' | 'funding' | ...
    last_open_time timestamptz,
    last_year_month text,
    rows_loaded bigint not null default 0,
    updated_at timestamptz not null default now(),
    constraint research_data_sync_state_unique unique (symbol, data_kind)
);

-- ---------------------------------------------------------------------------
-- Backtest runs + per-strategy results (incl. execution window)
-- ---------------------------------------------------------------------------
create table if not exists public.research_backtest_runs (
    id uuid primary key default gen_random_uuid(),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    period_start timestamptz,
    period_end timestamptz,
    symbols text[] not null,
    cost_taker_fee numeric not null,
    cost_slippage_bps numeric not null,
    leverage numeric not null default 1,
    notes text,
    meta jsonb not null default '{}'::jsonb
);

create table if not exists public.research_strategy_results (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references public.research_backtest_runs (id) on delete cascade,
    strategy_id text not null,
    family text not null,
    symbol text not null,
    timeframe text not null,
    params jsonb not null default '{}'::jsonb,
    total_return numeric,
    oos_return numeric,
    max_drawdown numeric,
    sharpe numeric,
    profit_factor numeric,
    win_rate numeric,
    score numeric,
    trades integer not null default 0,
    first_execution_at timestamptz,
    last_execution_at timestamptz,
    notes text,
    metrics jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint research_strategy_results_unique unique (run_id, strategy_id, symbol)
);

create index if not exists idx_research_strategy_results_run
    on public.research_strategy_results (run_id);

create index if not exists idx_research_strategy_results_score
    on public.research_strategy_results (score desc);
