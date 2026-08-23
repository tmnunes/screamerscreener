"use client";

import { useState } from "react";
import { refreshData } from "@/lib/api";

export function RefreshButton() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function onClick() {
    setLoading(true);
    setMessage(null);
    try {
      await refreshData();
      setMessage("Refresh complete");
      window.location.reload();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={onClick}
        disabled={loading}
        className="rounded bg-[var(--ink)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
      >
        {loading ? "Refreshing…" : "Refresh Data"}
      </button>
      {message ? <span className="text-xs text-[var(--muted)]">{message}</span> : null}
    </div>
  );
}
