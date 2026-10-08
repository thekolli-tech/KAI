import { connection } from "next/server";
import { ChatRequestError, readChatRequest } from "@kai/types";

import { jsonError } from "@/server/http";
import { chatStreamUrl, localBearerToken } from "@/server/upstream";

export async function POST(request: Request) {
  await connection();
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return jsonError(422);
  }
  let chat: { message: string; conversation_id: string };
  try {
    chat = readChatRequest(body);
  } catch (error) {
    if (error instanceof ChatRequestError) {
      return jsonError(422);
    }
    return jsonError(422);
  }
  const token = localBearerToken();
  if (token === "") {
    return jsonError(401);
  }
  let upstream: Response;
  try {
    upstream = await fetch(chatStreamUrl(), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({
        message: chat.message,
        conversation_id: chat.conversation_id,
      }),
      signal: request.signal,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return new Response(null, { status: 499 });
    }
    return jsonError(503);
  }
  if (!upstream.ok || upstream.body === null) {
    await upstream.body?.cancel();
    return jsonError(upstream.status);
  }
  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
