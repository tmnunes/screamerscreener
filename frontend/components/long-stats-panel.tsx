"use client";

import Link from "next/link";
import { formatPct, type LongHorizonStats, type LongPerformanceStats } from "@/lib/api";

function pctTone(value: number | null | undefined) {
  if (value === null || value === undefined) return "text-[var(--muted)]";
  if (value > 0) return "text-[var(--long)]";
  if (value < 0) return "text-[var(--short)]";
  return "text-[var(--ink)]";
}

function HorizonCell({
  label,
  stats,
}: {
  label: string;
  stats: LongHorizonStats | undefined;
}) {
  const count = stats?.count ?? 0;
  return (
    <div className="rounded border border-[var(--line)] bg-white p-3">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="text-xs font-semibold tracking-wide text-[var(--muted)]">
          {label}
        </span>
        <span className="text-[10px] text-[var(--muted)]">{count} signals</span>
      </div>
      <dl className="grid grid-cols-3 gap-2 text-sm">
        <div>
          <dt className="text-[10px] uppercase text-[var(--muted)]">Min</dt>
          <dd className={`font-mono ${pctTone(stats?.min)}`}>
            {formatPct(stats?.min)}
          </dd>
        </div>
        <div>
          <dt className="text-[10px] uppercase text-[var(--muted)]">Avg</dt>
          <dd className={`font-mono ${pctTone(stats?.avg)}`}>
            {formatPct(stats?.avg)}
          </dd>
        </div>
        <div>
          <dt className="text-[10px] uppercase text-[var(--muted)]">Max</dt>
          <dd className={`font-mono ${pctTone(stats?.max)}`}>
            {formatPct(stats?.max)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export function LongStatsPanel({
  data,
  title = "LONG performance",
  showByStock = false,
}: {
  data: LongPerformanceStats | null | undefined;
  title?: string;
  showByStock?: boolean;
}) {
  if (!data) {
    return (
      <p className="text-sm text-[var(--muted)]">LONG stats unavailable.</p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">
            {title}
          </h2>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Min / avg / max % return at +5 / +10 / +15 trading days after LONG ·{" "}
            {data.long_count} signal{data.long_count === 1 ? "" : "s"}
          </p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <HorizonCell label="+5D" stats={data.horizons["5d"]} />
        <HorizonCell label="+10D" stats={data.horizons["10d"]} />
        <HorizonCell label="+15D" stats={data.horizons["15d"]} />
      </div>

      {showByStock && data.by_stock && data.by_stock.length > 0 ? (
        <div className="overflow-x-auto rounded border border-[var(--line)] bg-white">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-[var(--line)] text-[10px] uppercase tracking-wide text-[var(--muted)]">
              <tr>
                <th className="px-3 py-2 font-medium">Stock</th>
                <th className="px-3 py-2 font-medium">n</th>
                <th className="px-3 py-2 font-medium">+5d avg</th>
                <th className="px-3 py-2 font-medium">+5d min/max</th>
                <th className="px-3 py-2 font-medium">+10d avg</th>
                <th className="px-3 py-2 font-medium">+10d min/max</th>
                <th className="px-3 py-2 font-medium">+15d avg</th>
                <th className="px-3 py-2 font-medium">+15d min/max</th>
              </tr>
            </thead>
            <tbody>
              {data.by_stock.map((row) => {
                const h5 = row.horizons["5d"];
                const h10 = row.horizons["10d"];
                const h15 = row.horizons["15d"];
                return (
                  <tr
                    key={row.ticker}
                    className="border-b border-[var(--line)] last:border-0"
                  >
                    <td className="px-3 py-2">
                      <Link
                        href={`/stocks/${row.ticker}`}
                        className="font-medium hover:underline"
                      >
                        {row.ticker}
                      </Link>
                      {row.name ? (
                        <div className="text-xs text-[var(--muted)]">{row.name}</div>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 font-mono text-[var(--muted)]">
                      {row.long_count}
                    </td>
                    <td className={`px-3 py-2 font-mono ${pctTone(h5?.avg)}`}>
                      {formatPct(h5?.avg)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-[var(--muted)]">
                      {formatPct(h5?.min)} / {formatPct(h5?.max)}
                    </td>
                    <td className={`px-3 py-2 font-mono ${pctTone(h10?.avg)}`}>
                      {formatPct(h10?.avg)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-[var(--muted)]">
                      {formatPct(h10?.min)} / {formatPct(h10?.max)}
                    </td>
                    <td className={`px-3 py-2 font-mono ${pctTone(h15?.avg)}`}>
                      {formatPct(h15?.avg)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-[var(--muted)]">
                      {formatPct(h15?.min)} / {formatPct(h15?.max)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      <p className="text-[10px] text-[var(--muted)]">{data.note}</p>
    </div>
  );
}
