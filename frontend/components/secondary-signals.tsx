import type { Trigger } from "@/lib/api";

export type Signal = "green" | "red" | "neutral";

export type SecondarySignals = {
  overall: Signal;
  score: number;
  green: number;
  red: number;
  neutral: number;
  categories: Record<string, Signal>;
  indicators: Array<{
    key: string;
    label: string;
    category: string;
    signal: Signal;
    hint: string;
  }>;
};

const CATEGORY_ORDER = [
  "TREND",
  "MOMENTUM",
  "VOLUME",
  "VOLATILITY",
  "PRICE ACTION",
  "MARKET REGIME",
] as const;

const signalStyles: Record<Signal, string> = {
  green: "bg-[var(--long)]",
  red: "bg-[var(--short)]",
  neutral: "bg-[#c9c4b8]",
};

const signalLabels: Record<Signal, string> = {
  green: "Supportive",
  red: "Against",
  neutral: "Neutral",
};

export function SignalDot({
  signal,
  size = "sm",
  title,
}: {
  signal: Signal;
  size?: "sm" | "md" | "lg";
  title?: string;
}) {
  const sizes = {
    sm: "h-2.5 w-2.5",
    md: "h-3.5 w-3.5",
    lg: "h-5 w-5",
  };
  return (
    <span
      title={title ?? signalLabels[signal]}
      className={`inline-block rounded-full ${sizes[size]} ${signalStyles[signal]}`}
    />
  );
}

export function SecondarySignalStrip({
  signals,
  compact = false,
}: {
  signals: SecondarySignals | null | undefined;
  compact?: boolean;
}) {
  if (!signals) {
    return (
      <span className="text-[10px] text-[var(--muted)]">No secondary data</span>
    );
  }

  const categories = CATEGORY_ORDER.filter((c) => signals.categories[c]);

  return (
    <div className={compact ? "flex items-center gap-2" : "space-y-2"}>
      <div className="flex items-center gap-2">
        <SignalDot signal={signals.overall} size={compact ? "sm" : "md"} />
        {!compact ? (
          <span className="text-xs font-medium">
            Secondary: {signalLabels[signals.overall]}
            <span className="ml-2 font-normal text-[var(--muted)]">
              ({signals.green}G · {signals.neutral}N · {signals.red}R)
            </span>
          </span>
        ) : (
          <span className="text-[10px] text-[var(--muted)]">
            {signalLabels[signals.overall]}
          </span>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {categories.map((cat) => (
          <span
            key={cat}
            className="inline-flex items-center gap-1 rounded border border-[var(--line)] bg-white px-1.5 py-0.5 text-[10px] text-[var(--muted)]"
            title={`${cat}: ${signalLabels[signals.categories[cat]]}`}
          >
            <SignalDot signal={signals.categories[cat]} size="sm" />
            {!compact ? cat.split(" ")[0] : cat.slice(0, 1)}
          </span>
        ))}
      </div>
    </div>
  );
}

export function SecondarySignalPanel({
  signals,
  triggerType,
}: {
  signals: SecondarySignals | null | undefined;
  triggerType: Trigger["trigger_type"];
}) {
  if (!signals) {
    return (
      <p className="text-sm text-[var(--muted)]">
        Secondary semáforos indisponíveis — corre o cálculo após a migration dos
        secundários.
      </p>
    );
  }

  const byCategory = new Map<string, typeof signals.indicators>();
  for (const ind of signals.indicators) {
    const list = byCategory.get(ind.category) ?? [];
    list.push(ind);
    byCategory.set(ind.category, list);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded border border-[var(--line)] bg-white p-4">
        <SignalDot signal={signals.overall} size="lg" />
        <div>
          <p className="font-medium">
            Overall: {signalLabels[signals.overall]}
          </p>
          <p className="text-xs text-[var(--muted)]">
            For a {triggerType} trigger · {signals.green} supportive ·{" "}
            {signals.neutral} neutral · {signals.red} against
          </p>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {CATEGORY_ORDER.map((cat) => {
          const items = byCategory.get(cat);
          if (!items?.length) return null;
          const catSignal = signals.categories[cat] ?? "neutral";
          return (
            <div
              key={cat}
              className="rounded border border-[var(--line)] bg-white p-3"
            >
              <div className="mb-2 flex items-center gap-2">
                <SignalDot signal={catSignal} />
                <h4 className="text-xs font-semibold tracking-wide text-[var(--muted)]">
                  {cat}
                </h4>
              </div>
              <ul className="space-y-1.5 text-xs">
                {items.map((ind) => (
                  <li key={ind.key} className="flex items-start justify-between gap-2">
                    <span className="flex items-center gap-2">
                      <SignalDot signal={ind.signal} size="sm" />
                      <span>{ind.label}</span>
                    </span>
                    <span className="text-right text-[var(--muted)]">{ind.hint}</span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}
