import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { TriggerCard } from "@/components/trigger-card";
import { RecentTimeline } from "@/components/recent-timeline";
import { RefreshCryptoButton } from "@/components/refresh-button";
import { LongStatsPanel } from "@/components/long-stats-panel";
import { UniverseTabs } from "@/components/universe-tabs";
import { MarketDataPanel } from "@/components/market-data-panel";
import {
  fetchCryptoOverview,
  fetchDataStatusCrypto,
  fetchLongPerformanceStats,
  fetchRecent,
  fetchStats,
  fetchToday,
  formatDay,
  formatPct,
  formatPrice,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function CryptoPage() {
  let today = null;
  let recent = null;
  let stats = null;
  let status = null;
  let longStats = null;
  let overview = null;
  let error: string | null = null;

  try {
    [today, recent, stats, status, longStats, overview] = await Promise.all([
      fetchToday("CRYPTO"),
      fetchRecent(7, "CRYPTO"),
      fetchStats("CRYPTO"),
      fetchDataStatusCrypto(),
      fetchLongPerformanceStats("CRYPTO"),
      fetchCryptoOverview(),
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load crypto data";
  }

  return (
    <>
      <SiteHeader active="crypto" />
      <main className="mx-auto w-full max-w-6xl px-6 py-8">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">
              Crypto screener
            </h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              TOP {overview?.top_n ?? status?.top_n ?? 25} · Vortex 47 / 1.6 ·
              FreeCryptoAPI · 24/7 daily candles (UTC date)
            </p>
          </div>
          <RefreshCryptoButton />
        </div>

        <UniverseTabs active="crypto" />

        {error ? (
          <div className="rounded border border-[var(--line)] bg-white p-4 text-sm text-[var(--short)]">
            {error}
            <p className="mt-2 text-[var(--muted)]">
              Apply migration 5, set FREECRYPTOAPI_API_KEY, then run{" "}
              <code className="font-mono text-xs">
                python -m backend.ingestion.initial_load_crypto
              </code>
            </p>
          </div>
        ) : (
          <>
            <section className="mb-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Last data" value={overview?.last_data ?? "—"} />
              <Stat
                label="Last refresh"
                value={
                  overview?.last_refresh
                    ? new Date(overview.last_refresh).toLocaleString()
                    : "—"
                }
              />
              <Stat
                label="Active cryptos"
                value={String(stats?.instruments ?? stats?.stocks ?? 0)}
              />
              <Stat
                label="Triggers today"
                value={`${stats?.today.long ?? 0} LONG · ${stats?.today.short ?? 0} SHORT · ${stats?.today.stop ?? 0} STOP`}
              />
            </section>

            <section className="mb-12 grid gap-8 lg:grid-cols-3">
              <TriggerColumn title="LONG" color="var(--long)" items={today?.long ?? []} />
              <TriggerColumn title="SHORT" color="var(--short)" items={today?.short ?? []} />
              <TriggerColumn title="STOP" color="var(--stop)" items={today?.stop ?? []} />
            </section>

            <section className="mb-12">
              <h2 className="mb-3 text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">
                TOP {overview?.top_n ?? 25}
              </h2>
              <div className="overflow-x-auto rounded border border-[var(--line)] bg-white">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead className="border-b border-[var(--line)] text-[10px] uppercase tracking-wide text-[var(--muted)]">
                    <tr>
                      <th className="px-3 py-2">Rank</th>
                      <th className="px-3 py-2">Crypto</th>
                      <th className="px-3 py-2">Price</th>
                      <th className="px-3 py-2">24h</th>
                      <th className="px-3 py-2">Trigger</th>
                      <th className="px-3 py-2">RSI</th>
                      <th className="px-3 py-2">ADX</th>
                      <th className="px-3 py-2">Rel Vol</th>
                      <th className="px-3 py-2">Trend</th>
                      <th className="px-3 py-2">Last trigger</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(overview?.rows ?? []).map((row) => (
                      <tr
                        key={row.ticker}
                        className="border-b border-[var(--line)] last:border-0"
                      >
                        <td className="px-3 py-2 font-mono text-[var(--muted)]">
                          {row.rank ?? "—"}
                        </td>
                        <td className="px-3 py-2">
                          <Link
                            href={`/crypto/${row.ticker}`}
                            className="font-medium hover:underline"
                          >
                            {row.ticker}
                          </Link>
                          <div className="text-xs text-[var(--muted)]">{row.name}</div>
                        </td>
                        <td className="px-3 py-2 font-mono">
                          {row.price != null ? formatPrice(row.price, "USD") : "—"}
                        </td>
                        <td className="px-3 py-2 font-mono">
                          {formatPct(row.change_24h)}
                        </td>
                        <td className="px-3 py-2">{row.trigger ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">
                          {row.rsi14 != null ? Number(row.rsi14).toFixed(0) : "—"}
                        </td>
                        <td className="px-3 py-2 font-mono">
                          {row.adx14 != null ? Number(row.adx14).toFixed(0) : "—"}
                        </td>
                        <td className="px-3 py-2 font-mono">
                          {row.relative_volume != null
                            ? `${Number(row.relative_volume).toFixed(2)}x`
                            : "—"}
                        </td>
                        <td className="px-3 py-2">{row.trend ?? "—"}</td>
                        <td className="px-3 py-2 text-xs text-[var(--muted)]">
                          {row.last_trigger ? (
                            <Link
                              href={`/triggers/${row.last_trigger.id}`}
                              className="hover:underline"
                            >
                              {row.last_trigger.trigger_type} ·{" "}
                              {formatDay(row.last_trigger.date)}
                            </Link>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <RecentTimeline days={recent?.days ?? []} />

            <section className="mt-12 border-t border-[var(--line)] pt-8">
              <LongStatsPanel
                data={longStats}
                showByStock
                title="LONG performance · Crypto"
              />
            </section>

            <section className="mt-12 border-t border-[var(--line)] pt-8">
              <MarketDataPanel
                title="MARKET DATA · CRYPTO"
                status={status}
                refreshSlot={<RefreshCryptoButton />}
              />
            </section>
          </>
        )}
      </main>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[var(--line)] bg-white p-4">
      <div className="text-xs tracking-wide text-[var(--muted)] uppercase">{label}</div>
      <div className="mt-2 text-sm font-medium">{value}</div>
    </div>
  );
}

function TriggerColumn({
  title,
  color,
  items,
}: {
  title: string;
  color: string;
  items: import("@/lib/api").Trigger[];
}) {
  return (
    <div>
      <h2
        className="mb-3 flex items-center gap-2 text-sm font-semibold tracking-[0.12em]"
        style={{ color }}
      >
        <span
          className="inline-block h-2.5 w-2.5 rounded-full"
          style={{ background: color }}
        />
        {title}
      </h2>
      <div className="rounded border border-[var(--line)] bg-white px-4">
        {items.length === 0 ? (
          <p className="py-6 text-sm text-[var(--muted)]">No triggers</p>
        ) : (
          items.map((t) => <TriggerCard key={t.id} trigger={t} />)
        )}
      </div>
    </div>
  );
}
