"use client";

import { useState } from "react";
import { refreshCrypto, refreshStocks } from "@/lib/api";

export function RefreshStocksButton() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function onClick() {
    setLoading(true);
    setMessage(null);
    try {
      await refreshStocks();
      setMessage("Stocks refresh complete");
      window.location.reload();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={onClick}
        disabled={loading}
        className="rounded border border-[var(--line)] bg-white px-3 py-1.5 text-sm font-medium hover:bg-[#faf8f4] disabled:opacity-50"
      >
        {loading ? "Refreshing stocks…" : "Refresh Stocks"}
      </button>
      {message ? (
        <span className="max-w-xs text-right text-[10px] text-[var(--muted)]">
          {message}
        </span>
      ) : null}
    </div>
  );
}

export function RefreshCryptoButton() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function onClick() {
    setLoading(true);
    setMessage(null);
    try {
      await refreshCrypto();
      setMessage("Crypto refresh complete");
      window.location.reload();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={onClick}
        disabled={loading}
        className="rounded border border-[var(--line)] bg-white px-3 py-1.5 text-sm font-medium hover:bg-[#faf8f4] disabled:opacity-50"
      >
        {loading ? "Refreshing crypto…" : "Refresh Crypto"}
      </button>
      {message ? (
        <span className="max-w-xs text-right text-[10px] text-[var(--muted)]">
          {message}
        </span>
      ) : null}
    </div>
  );
}

/** @deprecated use RefreshStocksButton */
export function RefreshButton() {
  return <RefreshStocksButton />;
}
