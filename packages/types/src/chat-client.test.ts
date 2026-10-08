import assert from "node:assert/strict";
import test from "node:test";

import { ChatHttpError } from "./chat.ts";
import { forwardSseBody, isAbortError, streamChat, workspaceChatStreamPath } from "./chat-client.ts";

const REQUEST = "33333333-3333-4333-8333-333333333333";
const RUN = "44444444-4444-4444-8444-444444444444";
const ORG = "22222222-2222-4222-8222-222222222222";

function frame(type: string, extra: Record<string, unknown> = {}): string {
  return `event: ${type}\ndata: ${JSON.stringify({
    type,
    request_id: REQUEST,
    run_id: RUN,
    organization_id: ORG,
    ...extra,
  })}\n\n`;
}

const completion = {
  message: "provider:mock",
  model_id: "mock-text",
  provider_id: "mock",
  verified: true,
};

test("streamChat posts to the same-origin route without a bearer token", async () => {
  const bodies = [
    frame("run.started"),
    frame("message.delta", { delta: "provider:" }),
    frame("message.delta", { delta: "mock" }),
    frame("message.completed", completion),
    frame("run.completed", completion),
  ];
  let authorization: string | null = "unset";
  let url = "";
  const fetchImpl: typeof fetch = async (input, init) => {
    url = String(input);
    authorization = new Headers(init?.headers).get("authorization");
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        const encoder = new TextEncoder();
        for (const body of bodies) {
          controller.enqueue(encoder.encode(body));
        }
        controller.close();
      },
    });
    return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
  };
  const events: string[] = [];
  const deltas: string[] = [];
  await streamChat({
    message: "Hello KAI",
    conversationId: "55555555-5555-4555-8555-555555555555",
    fetchImpl,
    onEvent(event) {
      events.push(event.type);
      if (event.type === "message.delta") {
        deltas.push(event.delta);
      }
    },
  });
  assert.equal(url, workspaceChatStreamPath);
  assert.equal(authorization, null);
  assert.deepEqual(events, [
    "run.started",
    "message.delta",
    "message.delta",
    "message.completed",
    "run.completed",
  ]);
  assert.equal(deltas.join(""), "provider:mock");
});

test("http 401 and 422 do not keep the response body", async () => {
  for (const status of [401, 422]) {
    const fetchImpl: typeof fetch = async () =>
      new Response(JSON.stringify({ message: "Bearer sk-live-secret" }), { status });
    await assert.rejects(
      () =>
        streamChat({
          message: "Hello",
          conversationId: "55555555-5555-4555-8555-555555555555",
          fetchImpl,
          onEvent() {},
        }),
      (error: unknown) => {
        assert.ok(error instanceof ChatHttpError);
        assert.equal(error.status, status);
        assert.equal(error.message.includes("sk-live"), false);
        return true;
      },
    );
  }
});

test("a network failure becomes a status-less http error", async () => {
  const fetchImpl: typeof fetch = async () => {
    throw new TypeError("connect ECONNREFUSED sk-live-secret");
  };
  await assert.rejects(
    () =>
      streamChat({
        message: "Hello",
        conversationId: "55555555-5555-4555-8555-555555555555",
        fetchImpl,
        onEvent() {},
      }),
    (error: unknown) => {
      assert.ok(error instanceof ChatHttpError);
      assert.equal(error.status, 0);
      assert.equal(error.message.includes("sk-live"), false);
      return true;
    },
  );
});

test("aborting the stream rejects with AbortError", async () => {
  const controller = new AbortController();
  const fetchImpl: typeof fetch = (_input, init) =>
    new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => {
        const error = new Error("The operation was aborted.");
        error.name = "AbortError";
        reject(error);
      });
    });
  const pending = streamChat({
    message: "Hello",
    conversationId: "55555555-5555-4555-8555-555555555555",
    signal: controller.signal,
    fetchImpl,
    onEvent() {},
  });
  controller.abort();
  await assert.rejects(pending, (error: unknown) => isAbortError(error));
});

test("the first SSE frame is forwarded before the rest of the body", async () => {
  const encoder = new TextEncoder();
  let releaseSecond = () => {};
  const gate = new Promise<void>((resolve) => {
    releaseSecond = resolve;
  });
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      controller.enqueue(encoder.encode(frame("message.delta", { delta: "provider:" })));
      await gate;
      controller.enqueue(encoder.encode(frame("message.delta", { delta: "mock" })));
      controller.close();
    },
  });
  const deltas: string[] = [];
  const forwarded = forwardSseBody(body, {
    onEvent(event) {
      if (event.type === "message.delta") {
        deltas.push(event.delta);
      }
    },
    onError() {
      throw new Error("stream failed");
    },
  });
  const reader = forwarded.getReader();
  const first = await Promise.race([
    reader.read(),
    new Promise<never>((_resolve, reject) => {
      setTimeout(() => reject(new Error("the stream was buffered")), 500);
    }),
  ]);
  assert.equal(first.done, false);
  assert.equal(new TextDecoder().decode(first.value).includes("provider:"), true);
  for (let attempt = 0; attempt < 20 && deltas.length === 0; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  assert.deepEqual(deltas, ["provider:"]);
  releaseSecond();
  await reader.read();
  await reader.read();
  for (let attempt = 0; attempt < 20 && deltas.length < 2; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  assert.deepEqual(deltas, ["provider:", "mock"]);
  reader.releaseLock();
});
