import { connection } from "next/server";

import { jsonError, authorizedFetch, proxyJson } from "@/server/http";
import { conversationUrl } from "@/server/upstream";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

type Context = { params: Promise<{ id: string }> };

export async function GET(_request: Request, context: Context) {
  await connection();
  const { id } = await context.params;
  if (!UUID_PATTERN.test(id)) {
    return jsonError(404);
  }
  return proxyJson(await authorizedFetch(conversationUrl(id), { method: "GET" }));
}
