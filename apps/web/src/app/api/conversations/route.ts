import { connection } from "next/server";

import { authorizedFetch, proxyJson } from "@/server/http";
import { conversationsUrl } from "@/server/upstream";

export async function GET() {
  await connection();
  return proxyJson(await authorizedFetch(conversationsUrl(), { method: "GET" }));
}

export async function POST() {
  await connection();
  return proxyJson(await authorizedFetch(conversationsUrl(), { method: "POST" }));
}
