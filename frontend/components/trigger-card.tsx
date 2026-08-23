"use client";

import Link from "next/link";
import type { Trigger } from "@/lib/api";
import { formatDay, formatPrice } from "@/lib/api";

const styles = {
  LONG: { label: "LONG", color: "text-[var(--long)]", dot: "bg-[var(--long)]" },
  SHORT: {
    label: "SHORT",
    color: "text-[var(--short)]",
    dot: "bg-[var(--short)]",
  },
  STOP: { label: "STOP", color: "text-[var(--stop)]", dot: "bg-[var(--stop)]" },
} as const;

export function TriggerCard({ trigger }: { trigger: Trigger }) {
  const style = styles[trigger.trigger_type];
  return (
    <Link
      href={`/stocks/${trigger.ticker}`}
      className="block border-b border-[var(--line)] py-3 transition hover:bg-[#faf8f4]"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className={`mb-1 flex items-center gap-2 text-xs font-medium ${style.color}`}>
            <span className={`h-2 w-2 rounded-full ${style.dot}`} />
            {style.label}
          </div>
          <div className="text-lg font-semibold tracking-tight">{trigger.ticker}</div>
          <div className="text-sm text-[var(--muted)]">{trigger.name}</div>
        </div>
        <div className="text-right text-sm">
          <div className="font-mono">
            {formatPrice(Number(trigger.trigger_price), trigger.currency)}
          </div>
          <div className="text-[var(--muted)]">{formatDay(trigger.date)}</div>
          <div className="text-xs text-[var(--muted)]">{trigger.exchange}</div>
        </div>
      </div>
    </Link>
  );
}

export function TriggerRow({ trigger }: { trigger: Trigger }) {
  const style = styles[trigger.trigger_type];
  return (
    <Link
      href={`/triggers/${trigger.id}`}
      className="flex items-center gap-3 py-1.5 text-sm hover:underline"
    >
      <span className={`h-2 w-2 rounded-full ${style.dot}`} />
      <span className="font-medium">{trigger.ticker}</span>
      <span className={style.color}>{style.label}</span>
    </Link>
  );
}
