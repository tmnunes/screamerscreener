import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SecondarySignalPanel } from "@/components/secondary-signals";
import { fetchTrigger, formatDay, formatPct, formatPrice } from "@/lib/api";

export const dynamic = "force-dynamic";

const HORIZONS = [
  { key: "1d" as const, label: "+1D", field: "return_1d" as const, days: 1 },
  { key: "3d" as const, label: "+3D", field: "return_3d" as const, days: 3 },
  { key: "5d" as const, label: "+5D", field: "return_5d" as const, days: 5 },
  { key: "10d" as const, label: "+10D", field: "return_10d" as const, days: 10 },
  { key: "20d" as const, label: "+20D", field: "return_20d" as const, days: 20 },
];

export default async function TriggerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let trigger = null;
  let error: string | null = null;

  try {
    trigger = await fetchTrigger(id);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load trigger";
  }

  const perf = trigger?.performance;
  const meta = trigger?.performance_meta;
  const futureDays = meta?.future_trading_days ?? 0;
  const isComplete = futureDays >= 20;

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-3xl px-6 py-8">
        <Link href="/dashboard" className="text-sm text-[var(--muted)] hover:underline">
          ← Dashboard
        </Link>

        {error || !trigger ? (
          <p className="mt-6 text-[var(--short)]">{error ?? "Not found"}</p>
        ) : (
          <>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight">
              {trigger.trigger_type} · {trigger.ticker}
            </h1>
            <p className="text-[var(--muted)]">
              {trigger.name} · {formatDay(trigger.date)}
            </p>

            <section className="mt-8 space-y-6 text-sm">
              <Block title="Trigger">
                <Row label="Date" value={trigger.date} />
                <Row label="Ticker" value={trigger.ticker ?? "—"} />
                <Row label="Type" value={trigger.trigger_type} />
                <Row
                  label="Price"
                  value={formatPrice(Number(trigger.trigger_price), trigger.currency)}
                />
              </Block>

              <Block title="Secondary semáforos">
                <p className="mb-4 text-xs text-[var(--muted)]">
                  Verde = secundários alinhados com este {trigger.trigger_type}.
                  Vermelho = contradizem. Neutro = inconclusivo. Não altera o trigger
                  Vortex.
                </p>
                <SecondarySignalPanel
                  signals={trigger.secondary_signals}
                  triggerType={trigger.trigger_type}
                />
              </Block>

              <Block title="Band values">
                <Row label="Upper" value={Number(trigger.upper).toFixed(4)} />
                <Row label="Lower" value={Number(trigger.lower).toFixed(4)} />
                <Row label="Basis" value={Number(trigger.basis).toFixed(4)} />
              </Block>

              <Block title="Previous values">
                <Row label="Previous Upper" value={num(trigger.previous_upper)} />
                <Row label="Previous Lower" value={num(trigger.previous_lower)} />
                <Row label="Previous Basis" value={num(trigger.previous_basis)} />
                <Row label="Previous Close" value={num(trigger.previous_close)} />
              </Block>

              <Block title="Performance">
                <div className="mb-4 space-y-2 rounded bg-[#faf8f4] p-3 text-xs text-[var(--muted)]">
                  <p>
                    <strong className="text-[var(--ink)]">How this works:</strong>{" "}
                    +1D / +3D / +5D measure the return at the close of the 1st, 3rd,
                    5th… <em>trading day after this trigger</em> — not calendar days,
                    and not data from before the trigger.
                  </p>
                  <p>
                    Your 1 year of history lets us compute full performance for{" "}
                    <strong className="text-[var(--ink)]">older triggers</strong>{" "}
                    (20+ trading days before the last candle). This trigger has{" "}
                    <strong className="text-[var(--ink)]">{futureDays}</strong> trading
                    day{futureDays === 1 ? "" : "s"} after it
                    {meta?.last_market_date
                      ? ` (last data: ${formatDay(meta.last_market_date)})`
                      : ""}
                    .
                  </p>
                  {!isComplete ? (
                    <p>
                      Dashboard highlights recent signals — they will look incomplete
                      until more daily candles arrive. See{" "}
                      <Link
                        href={`/stocks/${trigger.ticker}`}
                        className="underline"
                      >
                        {trigger.ticker} history
                      </Link>{" "}
                      for older triggers with full +20D metrics.
                    </p>
                  ) : null}
                </div>

                {HORIZONS.map(({ key, label, field, days }) => {
                  const available = meta?.horizons?.[key] ?? false;
                  const horizonDate = meta?.horizon_dates?.[key];
                  const value = perf?.[field];
                  const display =
                    value !== null && value !== undefined
                      ? formatPct(value)
                      : available
                        ? "N/A"
                        : "Pending";
                  const sublabel = horizonDate
                    ? `close ${formatDay(horizonDate)}`
                    : available
                      ? undefined
                      : `needs ${days} trading days after trigger`;

                  return (
                    <Row key={key} label={label} value={display} hint={sublabel} />
                  );
                })}
              </Block>
            </section>

            <div className="mt-8">
              <Link
                href={`/stocks/${trigger.ticker}`}
                className="text-sm font-medium underline"
              >
                View {trigger.ticker} trigger history
              </Link>
            </div>
          </>
        )}
      </main>
    </>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded border border-[var(--line)] bg-white p-4">
      <h2 className="mb-3 text-xs font-semibold tracking-[0.15em] text-[var(--muted)]">
        {title.toUpperCase()}
      </h2>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Row({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="flex justify-between gap-4 border-b border-[var(--line)] py-1.5 last:border-0">
      <span className="text-[var(--muted)]">{label}</span>
      <span className="text-right">
        <span className="font-mono">{value}</span>
        {hint ? (
          <span className="mt-0.5 block text-[10px] text-[var(--muted)]">{hint}</span>
        ) : null}
      </span>
    </div>
  );
}

function num(value: number | null | undefined) {
  if (value === null || value === undefined) return "N/A";
  return Number(value).toFixed(4);
}
