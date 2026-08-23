-- Phase 19: secondary indicators (informational only — do NOT drive triggers)

create table if not exists public.secondary_indicator_values_daily (
    id uuid primary key default gen_random_uuid(),
    instrument_id uuid not null references public.market_instruments (id) on delete cascade,
    date date not null,

    -- TREND
    ema20 numeric,
    ema50 numeric,
    ema200 numeric,
    sma200 numeric,
    adx14 numeric,

    -- MOMENTUM
    rsi14 numeric,
    macd numeric,
    macd_signal numeric,
    macd_hist numeric,
    roc14 numeric,
    stoch_k numeric,
    stoch_d numeric,

    -- VOLUME
    volume_sma20 numeric,
    relative_volume numeric,
    obv numeric,

    -- VOLATILITY
    atr14 numeric,
    atr_pct numeric,
    bb_width numeric,

    -- PRICE ACTION
    breakout_20d boolean,
    breakout_50d boolean,
    dist_52w_high numeric,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint secondary_indicator_values_daily_unique unique (instrument_id, date)
);

create index if not exists idx_secondary_indicator_values_daily_instrument_date
    on public.secondary_indicator_values_daily (instrument_id, date);

drop trigger if exists trg_secondary_indicator_values_daily_updated_at
    on public.secondary_indicator_values_daily;
create trigger trg_secondary_indicator_values_daily_updated_at
    before update on public.secondary_indicator_values_daily
    for each row execute function public.set_updated_at();

-- Market regime (one row per trading date; optional if SPY/QQQ ingested)
create table if not exists public.market_regime_daily (
    id uuid primary key default gen_random_uuid(),
    date date not null unique,
    spy_close numeric,
    spy_sma200 numeric,
    spy_above_sma200 boolean,
    qqq_close numeric,
    qqq_sma200 numeric,
    qqq_above_sma200 boolean,
    vix_close numeric,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_market_regime_daily_updated_at on public.market_regime_daily;
create trigger trg_market_regime_daily_updated_at
    before update on public.market_regime_daily
    for each row execute function public.set_updated_at();
