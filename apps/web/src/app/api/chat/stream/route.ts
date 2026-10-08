import { connection } from "next/server";
import {
  ChatRequestError,
  displayError,
  forwardSseBody,
  providerLabel,
  readChatRequest,
} from "@kai/types";

import { sessions } from "@/server/sessions";
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
  const conversation = sessions.get(chat.conversation_id);
  if (conversation === undefined) {
    return jsonError(404);
  }
  const user = sessions.appendUser(chat.conversation_id, chat.message);
  const assistant = sessions.beginAssistant(chat.conversation_id);
  if (user === undefined || assistant === undefined) {
    return jsonError(404);
  }
  const token = localBearerToken();
  if (token === "") {
    sessions.patchAssistant(chat.conversation_id, assistant.id, {
      status: "failed",
      error: displayError({ status: 401 }),
    });
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
    const aborted = error instanceof Error && error.name === "AbortError";
    sessions.patchAssistant(chat.conversation_id, assistant.id, {
      status: aborted ? "cancelled" : "failed",
      error: aborted ? null : displayError({}),
    });
    if (aborted) {
      return new Response(null, { status: 499 });
    }
    return jsonError(500);
  }
  if (!upstream.ok || upstream.body === null) {
    await upstream.body?.cancel();
    const status = publicStatus(upstream.status);
    sessions.patchAssistant(chat.conversation_id, assistant.id, {
      status: "failed",
      error: displayError({ status }),
    });
    return jsonError(status);
  }
  let content = "";
  const stream = forwardSseBody(upstream.body, {
    onEvent(event) {
      if (event.type === "message.delta") {
        content += event.delta;
        sessions.patchAssistant(chat.conversation_id, assistant.id, { content, status: "streaming" });
      } else if (event.type === "message.completed" || event.type === "run.completed") {
        content = event.message;
        sessions.patchAssistant(chat.conversation_id, assistant.id, {
          content,
          status: "completed",
          providerLabel: providerLabel(event.provider_id),
        });
      } else if (event.type === "run.failed") {
        sessions.patchAssistant(chat.conversation_id, assistant.id, {
          content,
          status: "failed",
          error: displayError({ message: event.error.message }),
        });
      }
    },
    onError(kind) {
      sessions.patchAssistant(chat.conversation_id, assistant.id, {
        content,
        status: kind === "cancelled" ? "cancelled" : "failed",
        error: kind === "cancelled" ? null : displayError({}),
      });
    },
  });
  request.signal.addEventListener("abort", () => {
    sessions.patchAssistant(chat.conversation_id, assistant.id, {
      status: "cancelled",
    });
  });
  return new Response(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}

function jsonError(status: number): Response {
  return Response.json(
    { message: displayError({ status }) },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

function publicStatus(status: number): number {
  if (status === 401 || status === 403 || status === 404 || status === 422 || status === 502 || status === 503) {
    return status;
  }
  return 500;
}
