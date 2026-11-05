import { LongStatsPanel } from "@/components/long-stats-panel";
import { MarketDataPanel } from "@/components/market-data-panel";
import { RecentTimeline } from "@/components/recent-timeline";
import { RefreshCryptoButton, RefreshStocksButton } from "@/components/refresh-button";
import { TriggerCard } from "@/components/trigger-card";
import {
  fetchCryptoOverview,
  fetchDataStatusCrypto,
  fetchDataStatusStocks,
  fetchLongPerformanceStats,
  fetchRecent,
  fetchStats,
  fetchToday,
  formatDay,
  formatPct,
  formatPrice,
  type AssetType,
  type Trigger,
} from "@/lib/api";
import Link from "next/link";

export function TriggerColumn({
  title,
  color,
  items,
}: {
  title: string;
  color: string;
  items: Trigger[];
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

export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[var(--line)] bg-white p-4">
      <div className="text-xs tracking-wide text-[var(--muted)] uppercase">
        {label}
      </div>
      <div className="mt-2 text-sm font-medium">{value}</div>
    </div>
  );
}

export async function StocksHeroStats() {
  const [today, stats, status] = await Promise.all([
    fetchToday("STOCK"),
    fetchStats("STOCK"),
    fetchDataStatusStocks(),
  ]);
  return (
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
    </>
  );
}

export async function StocksRecentSection() {
  const recent = await fetchRecent(30, "STOCK");
  return <RecentTimeline days={recent?.days ?? []} />;
}

export async function StocksLongStatsSection() {
  const longStats = await fetchLongPerformanceStats("STOCK");
  return (
    <section className="mt-12 border-t border-[var(--line)] pt-8">
      <LongStatsPanel data={longStats} showByStock title="LONG performance · Stocks" />
    </section>
  );
}

export async function StocksMarketDataSection() {
  const status = await fetchDataStatusStocks();
  return (
    <section className="mt-12 border-t border-[var(--line)] pt-8">
      <MarketDataPanel
        title="MARKET DATA · STOCKS"
        status={status}
        refreshSlot={<RefreshStocksButton />}
      />
    </section>
  );
}

export async function CryptoHeroStats() {
  const [today, stats, status] = await Promise.all([
    fetchToday("CRYPTO"),
    fetchStats("CRYPTO"),
    fetchDataStatusCrypto(),
  ]);
  return (
    <>
      <section className="mb-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Last data" value={status?.last_daily_candle ?? "—"} />
        <Stat
          label="Last refresh"
          value={
            status?.last_refresh
              ? new Date(status.last_refresh).toLocaleString()
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
    </>
  );
}

export async function CryptoOverviewSection() {
  const overview = await fetchCryptoOverview();
  return <CryptoOverviewTable overview={overview} />;
}

function CryptoOverviewTable({
  overview,
}: {
  overview: Awaited<ReturnType<typeof fetchCryptoOverview>> | null;
}) {
  return (
    <section className="mb-12">
      <h2 className="mb-3 text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">
        TOP {overview?.top_n ?? 25}
      </h2>
      {overview?.note ? (
        <p className="mb-3 text-xs text-[var(--short)]">{overview.note}</p>
      ) : null}
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
                <td className="px-3 py-2 font-mono">{formatPct(row.change_24h)}</td>
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
  );
}

export async function CryptoRecentSection() {
  const recent = await fetchRecent(7, "CRYPTO");
  return <RecentTimeline days={recent?.days ?? []} />;
}

export async function CryptoLongStatsSection() {
  const longStats = await fetchLongPerformanceStats("CRYPTO" satisfies AssetType);
  return (
    <section className="mt-12 border-t border-[var(--line)] pt-8">
      <LongStatsPanel data={longStats} showByStock title="LONG performance · Crypto" />
    </section>
  );
}

export async function CryptoMarketDataSection() {
  const status = await fetchDataStatusCrypto();
  return (
    <section className="mt-12 border-t border-[var(--line)] pt-8">
      <MarketDataPanel
        title="MARKET DATA · CRYPTO"
        status={status}
        refreshSlot={<RefreshCryptoButton />}
      />
    </section>
  );
}
