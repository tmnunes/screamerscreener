import { NextResponse } from "next/server";

const BACKEND = process.env.API_URL ?? "http://localhost:8000";

async function proxyRefresh(path: string) {
  const res = await fetch(`${BACKEND}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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

export async function POST() {
  return proxyRefresh("/api/refresh/stocks");
}
