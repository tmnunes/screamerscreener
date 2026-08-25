const API_URL = process.env.API_URL ?? "http://localhost:8000";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export type Trigger = {
  id: string;
  date: string;
  trigger_type: "LONG" | "SHORT" | "STOP";
  trigger_price: number;
  ticker?: string;
  name?: string;
  exchange?: string;
  country?: string;
  currency?: string;
  basis: number;
  upper: number;
  lower: number;
  previous_basis?: number;
  previous_upper?: number;
  previous_lower?: number;
  previous_close?: number;
  performance?: {
    return_1d: number | null;
    return_3d: number | null;
    return_5d: number | null;
    return_10d: number | null;
    return_15d: number | null;
    return_20d: number | null;
  } | null;
  performance_meta?: {
    future_trading_days: number;
    last_market_date: string | null;
    horizons: Record<"1d" | "3d" | "5d" | "10d" | "15d" | "20d", boolean>;
    horizon_dates?: Record<"1d" | "3d" | "5d" | "10d" | "15d" | "20d", string | null>;
  };
  secondary_signals?: {
    overall: "green" | "red" | "neutral";
    score: number;
    green: number;
    red: number;
    neutral: number;
    categories: Record<string, "green" | "red" | "neutral">;
    indicators: Array<{
      key: string;
      label: string;
      category: string;
      signal: "green" | "red" | "neutral";
      hint: string;
    }>;
  } | null;
};

export type AssetType = "STOCK" | "CRYPTO";

export const fetchToday = (assetType: AssetType = "STOCK") =>
  api<{
    date: string | null;
    asset_type?: AssetType;
    long: Trigger[];
    short: Trigger[];
    stop: Trigger[];
  }>(`/api/triggers/today?asset_type=${assetType}`);

export const fetchRecent = (days = 30, assetType: AssetType = "STOCK") =>
  api<{
    from: string | null;
    to: string | null;
    asset_type?: AssetType;
    days: Array<{
      date: string;
      long: Trigger[];
      short: Trigger[];
      stop: Trigger[];
      all: Trigger[];
    }>;
  }>(`/api/triggers/recent?days=${days}&asset_type=${assetType}`);

/** @deprecated use fetchRecent */
export const fetchWeek = () => fetchRecent(30);

export const fetchStats = (assetType: AssetType = "STOCK") =>
  api<{
    asset_type?: AssetType;
    stocks: number;
    instruments?: number;
    today: { date: string | null; long: number; short: number; stop: number };
    last_market_date: string | null;
  }>(`/api/stats?asset_type=${assetType}`);

export type LongHorizonStats = {
  min: number | null;
  max: number | null;
  avg: number | null;
  count: number;
};

export type LongPerformanceStats = {
  trigger_type: "LONG";
  long_count: number;
  horizons: Record<"5d" | "10d" | "15d", LongHorizonStats>;
  by_stock?: Array<{
    ticker: string;
    name?: string | null;
    long_count: number;
    horizons: Record<"5d" | "10d" | "15d", LongHorizonStats>;
  }>;
  note: string;
  ticker?: string;
  name?: string | null;
  asset_type?: AssetType;
};

export const fetchLongPerformanceStats = (assetType: AssetType = "STOCK") =>
  api<LongPerformanceStats>(
    `/api/stats/long-performance?asset_type=${assetType}`,
  );

export const fetchStockLongStats = (ticker: string) =>
  api<LongPerformanceStats>(`/api/stocks/${ticker}/long-stats`);

export type DataStatus = {
  asset_type?: AssetType;
  provider?: string;
  last_daily_candle: string | null;
  last_ingestion: string | null;
  last_calculation: string | null;
  last_refresh?: string | null;
  instruments: number;
  instruments_with_data: number;
  api_requests_used: number;
  api_requests_limit: number;
  max_requests_per_run?: number;
  status?: string;
  top_n?: number | null;
  stocks?: DataStatus;
  crypto?: DataStatus;
};

export const fetchDataStatus = () => api<DataStatus>("/api/data-status");

export const fetchDataStatusStocks = () =>
  api<DataStatus>("/api/data-status/stocks");

export const fetchDataStatusCrypto = () =>
  api<DataStatus>("/api/data-status/crypto");

export type CryptoOverviewRow = {
  rank: number | null;
  ticker: string;
  name: string;
  in_top_universe?: boolean;
  price: number | null;
  change_24h: number | null;
  trigger: string | null;
  rsi14: number | null;
  adx14: number | null;
  relative_volume: number | null;
  trend: string | null;
  last_trigger: { id: string; date: string; trigger_type: string } | null;
};

export const fetchCryptoOverview = () =>
  api<{
    top_n: number;
    last_data: string | null;
    last_refresh: string | null;
    rows: CryptoOverviewRow[];
    note?: string | null;
    live_quotes?: number;
  }>("/api/crypto/overview");

export const fetchStock = (ticker: string) =>
  api<Record<string, unknown>>(`/api/stocks/${ticker}`);

export const fetchPrices = (ticker: string) =>
  api<
    Array<{
      date: string;
      open: number;
      high: number;
      low: number;
      close: number;
      volume: number;
    }>
  >(`/api/stocks/${ticker}/prices`);

export const fetchIndicators = (ticker: string) =>
  api<
    Array<{
      date: string;
      basis: number;
      upper: number;
      lower: number;
    }>
  >(`/api/stocks/${ticker}/indicators`);

export const fetchSecondaryIndicators = (ticker: string) =>
  api<{
    ticker: string;
    latest: Record<string, unknown> | null;
    series: Array<Record<string, unknown>>;
    market_regime: Record<string, unknown> | null;
    note: string;
  }>(`/api/stocks/${ticker}/secondary-indicators`);

export const fetchStockTriggers = (ticker: string) =>
  api<Trigger[]>(`/api/stocks/${ticker}/triggers`);

export const fetchTrigger = (id: string) => api<Trigger>(`/api/triggers/${id}`);

export const refreshData = async () => {
  const res = await fetch("/api/backend/refresh", { method: "POST" });
  if (!res.ok) throw new Error((await res.text()) || `Request failed: ${res.status}`);
  return res.json() as Promise<{ status: string }>;
};

export const refreshStocks = async () => {
  const res = await fetch("/api/backend/refresh/stocks", { method: "POST" });
  if (!res.ok) throw new Error((await res.text()) || `Request failed: ${res.status}`);
  return res.json() as Promise<{ status: string }>;
};

export const refreshCrypto = async () => {
  const res = await fetch("/api/backend/refresh/crypto", { method: "POST" });
  if (!res.ok) throw new Error((await res.text()) || `Request failed: ${res.status}`);
  return res.json() as Promise<{ status: string }>;
};

export function formatPrice(value: number, currency?: string) {
  const prefix = currency === "EUR" ? "€" : currency === "USD" ? "$" : "";
  return `${prefix}${Number(value).toFixed(2)}`;
}

export function formatPct(value: number | null | undefined) {
  if (value === null || value === undefined) return "N/A";
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

export function formatDay(iso: string) {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

export function weekdayLabel(iso: string) {
  const d = new Date(`${iso}T00:00:00`);
  return d
    .toLocaleDateString("en-GB", { weekday: "short", day: "2-digit" })
    .toUpperCase();
}
