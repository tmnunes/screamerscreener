import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="border-b border-[var(--line)] bg-[var(--panel)]">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/dashboard" className="text-lg font-semibold tracking-tight">
          VORTEX SCREENER
        </Link>
        <nav className="flex gap-5 text-sm text-[var(--muted)]">
          <Link href="/dashboard" className="hover:text-[var(--ink)]">
            Dashboard
          </Link>
        </nav>
      </div>
    </header>
  );
}
