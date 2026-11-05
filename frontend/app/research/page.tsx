import { SiteHeader } from "@/components/site-header";
import { LongStatsPanel } from "@/components/long-stats-panel";
import { UniverseTabs } from "@/components/universe-tabs";
import { fetchLongPerformanceStats, type AssetType } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ResearchPage({
  searchParams,
}: {
  searchParams: Promise<{ universe?: string }>;
}) {
  const sp = await searchParams;
  const universe: AssetType =
    sp.universe?.toUpperCase() === "CRYPTO" ? "CRYPTO" : "STOCK";

  let longStats = null;
  let error: string | null = null;
  try {
    longStats = await fetchLongPerformanceStats(universe);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load research";
  }

  return (
    <>
      <SiteHeader active="research" />
      <main className="mx-auto w-full max-w-6xl px-6 py-8">
        <h1 className="text-3xl font-semibold tracking-tight">Research</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Vortex LONG forward returns — one universe at a time (never mixed).
        </p>

        <div className="mt-6">
          <UniverseTabs
            active={universe === "CRYPTO" ? "crypto" : "stocks"}
            stocksHref="/research?universe=STOCK"
            cryptoHref="/research?universe=CRYPTO"
          />
        </div>

        <p className="mb-6 text-xs text-[var(--muted)]">
          Viewing: <strong className="text-[var(--ink)]">{universe}</strong>. Use
          the Stocks / Crypto tabs above, or{" "}
          <a className="underline" href="/research?universe=STOCK">
            ?universe=STOCK
          </a>{" "}
          /{" "}
          <a className="underline" href="/research?universe=CRYPTO">
            ?universe=CRYPTO
          </a>
          .
        </p>

        {error ? (
          <p className="text-sm text-[var(--short)]">{error}</p>
        ) : (
          <LongStatsPanel
            data={longStats}
            showByStock
            title={`Vortex LONG · ${universe}`}
          />
        )}
      </main>
    </>
  );
}
