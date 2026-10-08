import {
  ChatContractError,
  ChatHttpError,
  parseConversationDetail,
  parseConversationList,
  parseConversationSummary,
  takeSseEvents,
  type ConversationDetail,
  type ConversationSummary,
  type RunEvent,
} from "./chat";

export { ChatHttpError } from "./chat";

export const workspaceConversationsPath = "/api/conversations";
export const workspaceChatStreamPath = "/api/chat/stream";

export async function createConversation(
  fetchImpl: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<ConversationSummary> {
  const response = await fetchImpl(workspaceConversationsPath, { method: "POST", signal });
  if (!response.ok) {
    throw new ChatHttpError(response.status);
  }
  return parseConversationSummary(await response.json());
}

export async function listConversations(
  fetchImpl: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<ConversationSummary[]> {
  const response = await fetchImpl(workspaceConversationsPath, { signal });
  if (!response.ok) {
    throw new ChatHttpError(response.status);
  }
  return parseConversationList(await response.json());
}

export async function loadConversation(
  id: string,
  fetchImpl: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<ConversationDetail> {
  const response = await fetchImpl(`${workspaceConversationsPath}/${id}`, { signal });
  if (!response.ok) {
    throw new ChatHttpError(response.status);
  }
  return parseConversationDetail(await response.json());
}

export async function streamChat(input: {
  message: string;
  conversationId: string;
  signal?: AbortSignal;
  fetchImpl?: typeof fetch;
  onEvent: (event: RunEvent) => void;
}): Promise<void> {
  const fetchImpl = input.fetchImpl ?? fetch;
  let response: Response;
  try {
    response = await fetchImpl(workspaceChatStreamPath, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({
        message: input.message,
        conversation_id: input.conversationId,
      }),
      signal: input.signal,
    });
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }
    throw new ChatHttpError(0);
  }
  if (!response.ok || response.body === null) {
    throw new ChatHttpError(response.status);
  }
  await readEventStream(response.body, input.onEvent);
}

export function forwardSseBody(
  body: ReadableStream<Uint8Array>,
  handlers: {
    onEvent: (event: RunEvent) => void;
    onError: (kind: "cancelled" | "failed") => void;
  },
): ReadableStream<Uint8Array> {
  const [clientBody, recordBody] = body.tee();
  void readEventStream(recordBody, handlers.onEvent).catch((error: unknown) => {
    handlers.onError(isAbortError(error) ? "cancelled" : "failed");
  });
  return clientBody;
}

export async function readEventStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: RunEvent) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const taken = takeSseEvents(buffer);
      buffer = taken.rest;
      for (const event of taken.events) {
        onEvent(event);
      }
    }
  } catch (error) {
    if (error instanceof ChatContractError || isAbortError(error)) {
      throw error;
    }
    throw new ChatContractError();
  } finally {
    reader.releaseLock();
  }
}

export function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}
