import Link from "next/link";

export function UniverseTabs({
  active,
  stocksHref = "/dashboard",
  cryptoHref = "/crypto",
}: {
  active: "stocks" | "crypto";
  stocksHref?: string;
  cryptoHref?: string;
}) {
  return (
    <div className="mb-6 flex gap-1 border-b border-[var(--line)]">
      <Link
        href={stocksHref}
        className={`px-4 py-2 text-sm font-medium ${
          active === "stocks"
            ? "border-b-2 border-[var(--ink)] text-[var(--ink)]"
            : "text-[var(--muted)] hover:text-[var(--ink)]"
        }`}
      >
        Stocks
      </Link>
      <Link
        href={cryptoHref}
        className={`px-4 py-2 text-sm font-medium ${
          active === "crypto"
            ? "border-b-2 border-[var(--ink)] text-[var(--ink)]"
            : "text-[var(--muted)] hover:text-[var(--ink)]"
        }`}
      >
        Crypto
      </Link>
    </div>
  );
}
