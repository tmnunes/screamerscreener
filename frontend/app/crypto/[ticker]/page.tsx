import { redirect } from "next/navigation";

export const revalidate = 60;

/** Crypto detail reuses the shared stock detail surface (same Vortex/UI). */
export default async function CryptoTickerPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  redirect(`/stocks/${ticker.toUpperCase()}`);
}
