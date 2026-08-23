-- Phase 3: seed initial instrument universe (idempotent)

insert into public.market_instruments
    (ticker, symbol, exchange, country, name, currency, active)
values
    ('GALP',  'GALP.LS',  'LS', 'Portugal', 'Galp Energia', 'EUR', true),
    ('EDP',   'EDP.LS',   'LS', 'Portugal', 'EDP', 'EUR', true),
    ('EDPR',  'EDPR.LS',  'LS', 'Portugal', 'EDP Renováveis', 'EUR', true),
    ('JMT',   'JMT.LS',   'LS', 'Portugal', 'Jerónimo Martins', 'EUR', true),
    ('BCP',   'BCP.LS',   'LS', 'Portugal', 'Banco Comercial Português', 'EUR', true),
    ('AAPL',  'AAPL.US',  'US', 'USA', 'Apple', 'USD', true),
    ('MSFT',  'MSFT.US',  'US', 'USA', 'Microsoft', 'USD', true),
    ('NVDA',  'NVDA.US',  'US', 'USA', 'NVIDIA', 'USD', true),
    ('AMZN',  'AMZN.US',  'US', 'USA', 'Amazon', 'USD', true),
    ('GOOGL', 'GOOGL.US', 'US', 'USA', 'Alphabet', 'USD', true),
    ('META',  'META.US',  'US', 'USA', 'Meta Platforms', 'USD', true),
    ('TSLA',  'TSLA.US',  'US', 'USA', 'Tesla', 'USD', true),
    ('AVGO',  'AVGO.US',  'US', 'USA', 'Broadcom', 'USD', true),
    ('AMD',   'AMD.US',   'US', 'USA', 'AMD', 'USD', true),
    ('JPM',   'JPM.US',   'US', 'USA', 'JPMorgan Chase', 'USD', true)
on conflict (ticker) do update set
    symbol = excluded.symbol,
    exchange = excluded.exchange,
    country = excluded.country,
    name = excluded.name,
    currency = excluded.currency,
    active = excluded.active,
    updated_at = now();
