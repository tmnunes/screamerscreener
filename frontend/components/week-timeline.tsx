"use client";

import { useMemo, useState } from "react";
import { TriggerRow } from "@/components/trigger-card";
import type { Trigger } from "@/lib/api";
import { weekdayLabel } from "@/lib/api";

type Day = {
  date: string;
  long: Trigger[];
  short: Trigger[];
  stop: Trigger[];
  all: Trigger[];
};

export function WeekTimeline({ days }: { days: Day[] }) {
  const [typeFilter, setTypeFilter] = useState<"ALL" | "LONG" | "SHORT" | "STOP">(
    "ALL",
  );
  const [marketFilter, setMarketFilter] = useState<"ALL" | "Portugal" | "USA">(
    "ALL",
  );

  const filtered = useMemo(() => {
    return days.map((day) => {
      let items = day.all;
      if (typeFilter !== "ALL") {
        items = items.filter((t) => t.trigger_type === typeFilter);
      }
      if (marketFilter !== "ALL") {
        items = items.filter((t) => t.country === marketFilter);
      }
      return { ...day, items };
    });
  }, [days, typeFilter, marketFilter]);

  return (
    <section>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">
          LAST 7 DAYS
        </h2>
        <div className="flex flex-wrap gap-2 text-xs">
          {(["ALL", "LONG", "SHORT", "STOP"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTypeFilter(t)}
              className={`rounded border px-2 py-1 ${
                typeFilter === t
                  ? "border-[var(--ink)] bg-[var(--ink)] text-white"
                  : "border-[var(--line)] bg-white"
              }`}
            >
              {t}
            </button>
          ))}
          {(["ALL", "Portugal", "USA"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMarketFilter(m)}
              className={`rounded border px-2 py-1 ${
                marketFilter === m
                  ? "border-[var(--ink)] bg-[var(--ink)] text-white"
                  : "border-[var(--line)] bg-white"
              }`}
            >
              {m === "ALL" ? "All markets" : m}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-6">
        {filtered.map((day) => (
          <div key={day.date} className="border-t border-[var(--line)] pt-3">
            <div className="mb-2 font-mono text-xs tracking-wide text-[var(--muted)]">
              {weekdayLabel(day.date)}
            </div>
            {day.items.length === 0 ? (
              <p className="text-sm text-[var(--muted)]">No triggers</p>
            ) : (
              day.items.map((t) => <TriggerRow key={t.id} trigger={t} />)
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
