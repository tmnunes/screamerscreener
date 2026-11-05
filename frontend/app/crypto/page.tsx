import { Suspense } from "react";
import { SiteHeader } from "@/components/site-header";
import { RefreshCryptoButton } from "@/components/refresh-button";
import { UniverseTabs } from "@/components/universe-tabs";
import { LoadingBlock } from "@/components/loading-block";
import {
  CryptoHeroStats,
  CryptoLongStatsSection,
  CryptoMarketDataSection,
  CryptoOverviewSection,
  CryptoRecentSection,
} from "@/components/dashboard-sections";

export const dynamic = "force-dynamic";

export default function CryptoPage() {
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
              TOP 25 · Vortex 47 / 1.6 · FreeCryptoAPI · 24/7 daily candles (UTC
              date)
            </p>
          </div>
          <RefreshCryptoButton />
        </div>

        <UniverseTabs active="crypto" />

        <Suspense fallback={<LoadingBlock label="Loading today’s triggers…" />}>
          <CryptoHeroStats />
        </Suspense>

        <Suspense fallback={<LoadingBlock label="Loading TOP table…" />}>
          <CryptoOverviewSection />
        </Suspense>

        <Suspense fallback={<LoadingBlock label="Loading recent timeline…" />}>
          <CryptoRecentSection />
        </Suspense>

        <Suspense fallback={<LoadingBlock label="Loading LONG stats…" />}>
          <CryptoLongStatsSection />
        </Suspense>

        <Suspense fallback={<LoadingBlock label="Loading market data…" />}>
          <CryptoMarketDataSection />
        </Suspense>
      </main>
    </>
  );
}
