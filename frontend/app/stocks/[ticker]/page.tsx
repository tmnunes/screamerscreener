import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { VortexChart } from "@/components/vortex-chart";
import {
  fetchIndicators,
  fetchPrices,
  fetchStock,
  fetchStockTriggers,
  formatDay,
  formatPrice,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function StockPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  const upper = ticker.toUpperCase();

  let stock: Record<string, unknown> | null = null;
  let prices: Awaited<ReturnType<typeof fetchPrices>> = [];
  let indicators: Awaited<ReturnType<typeof fetchIndicators>> = [];
  let triggers: Awaited<ReturnType<typeof fetchStockTriggers>> = [];
  let error: string | null = null;

  try {
    [stock, prices, indicators, triggers] = await Promise.all([
      fetchStock(upper),
      fetchPrices(upper),
      fetchIndicators(upper),
      fetchStockTriggers(upper),
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load stock";
  }

  const vortex = (stock?.vortex ?? {}) as {
    length?: number;
    mult?: number;
    source?: string;
    timeframe?: string;
  };

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-6xl px-6 py-8">
        <Link href="/dashboard" className="text-sm text-[var(--muted)] hover:underline">
          ← Dashboard
        </Link>

        {error || !stock ? (
          <p className="mt-6 text-[var(--short)]">{error ?? "Not found"}</p>
        ) : (
          <>
            <div className="mt-4 mb-8">
              <h1 className="text-3xl font-semibold tracking-tight">
                {String(stock.ticker)}
              </h1>
              <p className="text-[var(--muted)]">
                {String(stock.name)} · {String(stock.exchange)} · {String(stock.currency)}
              </p>
            </div>

            <section className="mb-8 rounded border border-[var(--line)] bg-white p-4 text-sm">
              <h2 className="mb-3 text-xs font-semibold tracking-[0.15em] text-[var(--muted)]">
                VORTEX SETTINGS
              </h2>
              <div className="grid gap-2 sm:grid-cols-4">
                <div>Length {vortex.length ?? 47}</div>
                <div>Multiplier {vortex.mult ?? 1.6}</div>
                <div>Source {(vortex.source ?? "hlc3").toUpperCase()}</div>
                <div>Timeframe {vortex.timeframe ?? "Daily"}</div>
              </div>
            </section>

            <section className="mb-10 rounded border border-[var(--line)] bg-white p-2">
              <VortexChart
                prices={prices}
                indicators={indicators}
                triggers={triggers.map((t) => ({
                  date: t.date,
                  trigger_type: t.trigger_type,
                  trigger_price: Number(t.trigger_price),
                }))}
              />
            </section>

            <section className="mb-10">
              <h2 className="mb-3 text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">
                TRIGGER HISTORY
              </h2>
              <div className="rounded border border-[var(--line)] bg-white">
                {triggers.length === 0 ? (
                  <p className="p-4 text-sm text-[var(--muted)]">No triggers yet</p>
                ) : (
                  <ul>
                    {triggers.map((t) => (
                      <li key={t.id} className="border-b border-[var(--line)] px-4 py-3 text-sm">
                        <Link href={`/triggers/${t.id}`} className="flex justify-between gap-3 hover:underline">
                          <span>
                            <span className="font-medium">{t.trigger_type}</span>
                            <span className="text-[var(--muted)]"> · {formatDay(t.date)}</span>
                          </span>
                          <span className="font-mono">
                            {formatPrice(Number(t.trigger_price), String(stock.currency))}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>

            <section>
              <h2 className="mb-3 text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">
                SECONDARY INDICATORS
              </h2>
              <p className="rounded border border-dashed border-[var(--line)] bg-white p-4 text-sm text-[var(--muted)]">
                Coming in next phase
              </p>
            </section>
          </>
        )}
      </main>
    </>
  );
}
