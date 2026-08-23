const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    return_20d: number | null;
  } | null;
  performance_meta?: {
    future_trading_days: number;
    last_market_date: string | null;
    horizons: Record<"1d" | "3d" | "5d" | "10d" | "20d", boolean>;
    horizon_dates?: Record<"1d" | "3d" | "5d" | "10d" | "20d", string | null>;
  };
};

export const fetchToday = () =>
  api<{
    date: string | null;
    long: Trigger[];
    short: Trigger[];
    stop: Trigger[];
  }>("/api/triggers/today");

export const fetchRecent = (days = 30) =>
  api<{
    from: string | null;
    to: string | null;
    days: Array<{
      date: string;
      long: Trigger[];
      short: Trigger[];
      stop: Trigger[];
      all: Trigger[];
    }>;
  }>(`/api/triggers/recent?days=${days}`);

/** @deprecated use fetchRecent */
export const fetchWeek = () => fetchRecent(30);

export const fetchStats = () =>
  api<{
    stocks: number;
    today: { date: string | null; long: number; short: number; stop: number };
    last_market_date: string | null;
  }>("/api/stats");

export const fetchDataStatus = () =>
  api<{
    last_daily_candle: string | null;
    last_ingestion: string | null;
    last_calculation: string | null;
    instruments: number;
    instruments_with_data: number;
    api_requests_used: number;
    api_requests_limit: number;
  }>("/api/data-status");

export const fetchStock = (ticker: string) => api<Record<string, unknown>>(`/api/stocks/${ticker}`);

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

export const refreshData = () =>
  api<{ status: string }>("/api/refresh", { method: "POST" });

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
