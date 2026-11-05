export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="animate-pulse rounded border border-[var(--line)] bg-white px-4 py-8 text-sm text-[var(--muted)]">
      {label}
    </div>
  );
}
