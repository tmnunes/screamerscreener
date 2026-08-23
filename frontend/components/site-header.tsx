import Link from "next/link";

export function SiteHeader({
  active,
}: {
  active?: "stocks" | "crypto" | "research";
}) {
  return (
    <header className="border-b border-[var(--line)] bg-[var(--panel)]">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/dashboard" className="text-lg font-semibold tracking-tight">
          ScreamerScreener
        </Link>
        <nav className="flex gap-5 text-sm text-[var(--muted)]">
          <Link
            href="/dashboard"
            className={
              active === "stocks" ? "text-[var(--ink)]" : "hover:text-[var(--ink)]"
            }
          >
            Stocks
          </Link>
          <Link
            href="/crypto"
            className={
              active === "crypto" ? "text-[var(--ink)]" : "hover:text-[var(--ink)]"
            }
          >
            Crypto
          </Link>
          <Link
            href="/research"
            className={
              active === "research"
                ? "text-[var(--ink)]"
                : "hover:text-[var(--ink)]"
            }
          >
            Research
          </Link>
        </nav>
      </div>
    </header>
  );
}
