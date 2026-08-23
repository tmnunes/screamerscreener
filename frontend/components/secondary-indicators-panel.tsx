type Props = {
  latest: Record<string, unknown> | null;
  marketRegime: Record<string, unknown> | null;
  note?: string;
};

function fmt(value: unknown, digits = 2): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return n.toFixed(digits);
}

function fmtPct(value: unknown): string {
  if (value === null || value === undefined) return "—";
  const n = Number(value) * 100;
  if (Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function Group({
  title,
  items,
}: {
  title: string;
  items: Array<{ label: string; value: string }>;
}) {
  return (
    <div className="rounded border border-[var(--line)] bg-white p-4">
      <h3 className="mb-3 text-xs font-semibold tracking-[0.15em] text-[var(--muted)]">
        {title}
      </h3>
      <dl className="space-y-2 text-sm">
        {items.map((item) => (
          <div
            key={item.label}
            className="flex justify-between gap-3 border-b border-[var(--line)] py-1 last:border-0"
          >
            <dt className="text-[var(--muted)]">{item.label}</dt>
            <dd className="font-mono">{item.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function SecondaryIndicatorsPanel({ latest, marketRegime, note }: Props) {
  if (!latest) {
    return (
      <p className="rounded border border-dashed border-[var(--line)] bg-white p-4 text-sm text-[var(--muted)]">
        No secondary indicators yet. Run calculation after applying the secondary
        indicators migration.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-[var(--muted)]">
        As of {String(latest.date)} · Informational only — does not create or block
        LONG / SHORT / STOP triggers.
        {note ? ` ${note}` : ""}
      </p>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Group
          title="TREND"
          items={[
            { label: "EMA20", value: fmt(latest.ema20) },
            { label: "EMA50", value: fmt(latest.ema50) },
            { label: "EMA200", value: fmt(latest.ema200) },
            { label: "SMA200", value: fmt(latest.sma200) },
            { label: "ADX14", value: fmt(latest.adx14) },
          ]}
        />
        <Group
          title="MOMENTUM"
          items={[
            { label: "RSI14", value: fmt(latest.rsi14) },
            { label: "MACD", value: fmt(latest.macd, 4) },
            { label: "MACD Signal", value: fmt(latest.macd_signal, 4) },
            { label: "MACD Hist", value: fmt(latest.macd_hist, 4) },
            { label: "ROC14", value: fmt(latest.roc14) },
            { label: "Stoch %K", value: fmt(latest.stoch_k) },
            { label: "Stoch %D", value: fmt(latest.stoch_d) },
          ]}
        />
        <Group
          title="VOLUME"
          items={[
            { label: "Volume SMA20", value: fmt(latest.volume_sma20, 0) },
            { label: "Relative Volume", value: fmt(latest.relative_volume) },
            { label: "OBV", value: fmt(latest.obv, 0) },
          ]}
        />
        <Group
          title="VOLATILITY"
          items={[
            { label: "ATR14", value: fmt(latest.atr14) },
            { label: "ATR%", value: fmt(latest.atr_pct) },
            { label: "BB Width", value: fmt(latest.bb_width, 4) },
          ]}
        />
        <Group
          title="PRICE ACTION"
          items={[
            { label: "20D Breakout", value: fmt(latest.breakout_20d) },
            { label: "50D Breakout", value: fmt(latest.breakout_50d) },
            { label: "52W High Distance", value: fmtPct(latest.dist_52w_high) },
          ]}
        />
        <Group
          title="MARKET REGIME"
          items={
            marketRegime
              ? [
                  {
                    label: "SPY > SMA200",
                    value: fmt(marketRegime.spy_above_sma200),
                  },
                  {
                    label: "QQQ > SMA200",
                    value: fmt(marketRegime.qqq_above_sma200),
                  },
                  { label: "VIX", value: fmt(marketRegime.vix_close) },
                ]
              : [
                  {
                    label: "Status",
                    value: "SPY/QQQ not loaded (optional)",
                  },
                ]
          }
        />
      </div>
    </div>
  );
}
