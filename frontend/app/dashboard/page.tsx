import { Suspense } from "react";
import { SiteHeader } from "@/components/site-header";
import { RefreshStocksButton } from "@/components/refresh-button";
import { UniverseTabs } from "@/components/universe-tabs";
import { LoadingBlock } from "@/components/loading-block";
import {
  StocksHeroStats,
  StocksLongStatsSection,
  StocksMarketDataSection,
  StocksRecentSection,
} from "@/components/dashboard-sections";

// Request-time only — needs live FastAPI data (cannot prerender at build).
export const dynamic = "force-dynamic";

export default function DashboardPage() {
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

        <Suspense fallback={<LoadingBlock label="Loading today’s triggers…" />}>
          <StocksHeroStats />
        </Suspense>

        <Suspense fallback={<LoadingBlock label="Loading recent timeline…" />}>
          <StocksRecentSection />
        </Suspense>

        <Suspense fallback={<LoadingBlock label="Loading LONG stats…" />}>
          <StocksLongStatsSection />
        </Suspense>

        <Suspense fallback={<LoadingBlock label="Loading market data…" />}>
          <StocksMarketDataSection />
        </Suspense>
      </main>
    </>
  );
}
