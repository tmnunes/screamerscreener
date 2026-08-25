import { NextResponse } from "next/server";

const BACKEND = process.env.API_URL ?? "http://localhost:8000";

function cronHeaders(): HeadersInit {
  const secret = process.env.CRON_SECRET?.trim();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (secret) {
    headers["X-Cron-Secret"] = secret;
  }
  return headers;
}

export async function proxyRefresh(path: string) {
  const res = await fetch(`${BACKEND}${path}`, {
    method: "POST",
    headers: cronHeaders(),
    cache: "no-store",
  });
  const text = await res.text();
  let body: unknown = text;
  try {
    body = JSON.parse(text);
  } catch {
    /* keep text */
  }
  return NextResponse.json(body, { status: res.status });
}
