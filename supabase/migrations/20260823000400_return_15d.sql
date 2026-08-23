-- Add +15 trading-day forward return for LONG/SHORT/STOP performance stats.

alter table public.trigger_performance
    add column if not exists return_15d numeric;
