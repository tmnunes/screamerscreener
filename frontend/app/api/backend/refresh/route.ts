import { proxyRefresh } from "@/lib/backend-proxy";

export async function POST() {
  return proxyRefresh("/api/refresh");
}
