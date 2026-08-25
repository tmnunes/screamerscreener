import { NextResponse } from "next/server";

const BACKEND = process.env.API_URL ?? "http://localhost:8000";

export async function POST() {
  const res = await fetch(`${BACKEND}/api/refresh`, {
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
