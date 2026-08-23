import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { fetchTrigger, formatDay, formatPct, formatPrice } from "@/lib/api";

export const dynamic = "force-dynamic";

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
                <Row label="+1D" value={formatPct(perf?.return_1d)} />
                <Row label="+3D" value={formatPct(perf?.return_3d)} />
                <Row label="+5D" value={formatPct(perf?.return_5d)} />
                <Row label="+10D" value={formatPct(perf?.return_10d)} />
                <Row label="+20D" value={formatPct(perf?.return_20d)} />
              </Block>
            </section>

            <div className="mt-8">
              <Link
                href={`/stocks/${trigger.ticker}`}
                className="text-sm font-medium underline"
              >
                View {trigger.ticker} chart
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

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-[var(--line)] py-1.5 last:border-0">
      <span className="text-[var(--muted)]">{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );
}

function num(value: number | null | undefined) {
  if (value === null || value === undefined) return "N/A";
  return Number(value).toFixed(4);
}
