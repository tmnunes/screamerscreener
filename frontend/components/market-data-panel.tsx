import type { ReactNode } from "react";
import type { DataStatus } from "@/lib/api";

export function MarketDataPanel({
  title,
  status,
  refreshSlot,
}: {
  title: string;
  status: DataStatus | null | undefined;
  refreshSlot?: ReactNode;
}) {
  const ok = status?.status === "up_to_date" || Boolean(status?.last_daily_candle);
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">
          {title}
        </h2>
        {refreshSlot}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 text-sm">
        <StatusRow label="Last candle" value={status?.last_daily_candle ?? "—"} />
        <StatusRow
          label="Last refresh"
          value={
            status?.last_refresh
              ? new Date(status.last_refresh).toLocaleString()
              : "—"
          }
        />
        <StatusRow label="API" value={status?.provider ?? "—"} />
        <StatusRow
          label="Requests"
          value={`${status?.api_requests_used ?? 0} / ${status?.api_requests_limit ?? "—"}`}
        />
        <StatusRow
          label="Instruments"
          value={`${status?.instruments_with_data ?? 0} / ${status?.instruments ?? 0}`}
        />
        <StatusRow
          label="Status"
          value={ok ? "Up to date" : "No data"}
        />
      </div>
    </div>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-[var(--line)] py-2">
      <span className="text-[var(--muted)]">{label}</span>
      <span className="font-mono text-right">{value}</span>
    </div>
  );
}
