import { SiteHeader } from "@/components/site-header";
import { TriggerCard } from "@/components/trigger-card";
import { WeekTimeline } from "@/components/week-timeline";
import { RefreshButton } from "@/components/refresh-button";
import {
  fetchDataStatus,
  fetchStats,
  fetchToday,
  fetchWeek,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  let today = null;
  let week = null;
  let stats = null;
  let status = null;
  let error: string | null = null;

  try {
    [today, week, stats, status] = await Promise.all([
      fetchToday(),
      fetchWeek(),
      fetchStats(),
      fetchDataStatus(),
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load dashboard data";
  }

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-6xl px-6 py-8">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Dashboard</h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Daily Vortex Bands triggers · Length 47 · Mult 1.6 · HLC3
            </p>
          </div>
          <RefreshButton />
        </div>

        {error ? (
          <div className="rounded border border-[var(--line)] bg-white p-4 text-sm text-[var(--short)]">
            {error}
            <p className="mt-2 text-[var(--muted)]">
              Ensure the API is running on NEXT_PUBLIC_API_URL and migrations are applied.
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

            <WeekTimeline days={week?.days ?? []} />

            <section className="mt-12 border-t border-[var(--line)] pt-8">
              <h2 className="mb-4 text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">
                DATA STATUS
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 text-sm">
                <StatusRow label="Last daily candle" value={status?.last_daily_candle ?? "—"} />
                <StatusRow
                  label="Last ingestion"
                  value={
                    status?.last_ingestion
                      ? new Date(status.last_ingestion).toLocaleString()
                      : "—"
                  }
                />
                <StatusRow
                  label="Last calculation"
                  value={
                    status?.last_calculation
                      ? new Date(status.last_calculation).toLocaleString()
                      : "—"
                  }
                />
                <StatusRow label="Instruments" value={String(status?.instruments ?? 0)} />
                <StatusRow
                  label="Instruments with data"
                  value={String(status?.instruments_with_data ?? 0)}
                />
                <StatusRow
                  label="API requests used"
                  value={`${status?.api_requests_used ?? 0} / ${status?.api_requests_limit ?? 20}`}
                />
              </div>
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

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-[var(--line)] py-2">
      <span className="text-[var(--muted)]">{label}</span>
      <span className="font-mono text-right">{value}</span>
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
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold tracking-[0.12em]" style={{ color }}>
        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} />
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
