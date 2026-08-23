import { SiteHeader } from "@/components/site-header";
import { TriggerCard } from "@/components/trigger-card";
import { RecentTimeline } from "@/components/recent-timeline";
import { RefreshStocksButton } from "@/components/refresh-button";
import { LongStatsPanel } from "@/components/long-stats-panel";
import { UniverseTabs } from "@/components/universe-tabs";
import { MarketDataPanel } from "@/components/market-data-panel";
import {
  fetchDataStatusStocks,
  fetchLongPerformanceStats,
  fetchRecent,
  fetchStats,
  fetchToday,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  let today = null;
  let recent = null;
  let stats = null;
  let status = null;
  let longStats = null;
  let error: string | null = null;

  try {
    [today, recent, stats, status, longStats] = await Promise.all([
      fetchToday("STOCK"),
      fetchRecent(30, "STOCK"),
      fetchStats("STOCK"),
      fetchDataStatusStocks(),
      fetchLongPerformanceStats("STOCK"),
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load dashboard data";
  }

  return (
    <>
      <SiteHeader active="stocks" />
      <main className="mx-auto w-full max-w-6xl px-6 py-8">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">
              Stocks screener
            </h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Daily triggers · Length 47 · Mult 1.6 · HLC3 · EODHD
            </p>
          </div>
          <RefreshStocksButton />
        </div>

        <UniverseTabs active="stocks" />

        {error ? (
          <div className="rounded border border-[var(--line)] bg-white p-4 text-sm text-[var(--short)]">
            {error}
            <p className="mt-2 text-[var(--muted)]">
              Ensure the API is running and migration 5 (asset_type) is applied.
            </p>
          </div>
        ) : (
          <>
            <section className="mb-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Last market data" value={status?.last_daily_candle ?? "—"} />
              <Stat
                label="Last calculation"
                value={
                  status?.last_calculation
                    ? new Date(status.last_calculation).toLocaleString()
                    : "—"
                }
              />
              <Stat label="Stocks" value={String(stats?.stocks ?? 0)} />
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

            <RecentTimeline days={recent?.days ?? []} />

            <section className="mt-12 border-t border-[var(--line)] pt-8">
              <LongStatsPanel data={longStats} showByStock title="LONG performance · Stocks" />
            </section>

            <section className="mt-12 border-t border-[var(--line)] pt-8">
              <MarketDataPanel
                title="MARKET DATA · STOCKS"
                status={status}
                refreshSlot={<RefreshStocksButton />}
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
