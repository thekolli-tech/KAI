import assert from "node:assert/strict";
import test from "node:test";

import { ChatContractError, ChatRequestError, parseRunEvent, readChatRequest, takeSseEvents } from "./chat.ts";

const REQUEST = "33333333-3333-4333-8333-333333333333";
const RUN = "44444444-4444-4444-8444-444444444444";
const ORG = "22222222-2222-4222-8222-222222222222";
const CONVERSATION = "55555555-5555-4555-8555-555555555555";

function frame(type: string, extra: Record<string, unknown> = {}): string {
  return `event: ${type}\ndata: ${JSON.stringify({
    type,
    request_id: REQUEST,
    run_id: RUN,
    organization_id: ORG,
    ...extra,
  })}\n\n`;
}

test("parseRunEvent keeps the public correlation fields", () => {
  const event = parseRunEvent({
    type: "run.started",
    request_id: REQUEST,
    run_id: RUN,
    organization_id: ORG,
  });
  assert.equal(event.type, "run.started");
  assert.equal(event.request_id, REQUEST);
  assert.equal(event.run_id, RUN);
  assert.equal(event.organization_id, ORG);
});

test("takeSseEvents reads a split stream without waiting for the rest", () => {
  const first = frame("message.delta", { delta: "provider:" }).slice(0, 20);
  const rest = frame("message.delta", { delta: "provider:" }).slice(20);
  const partial = takeSseEvents(first);
  assert.deepEqual(partial.events, []);
  const done = takeSseEvents(partial.rest + rest + frame("message.delta", { delta: "mock" }));
  assert.equal(done.events.length, 2);
  assert.equal(done.events[0]?.type, "message.delta");
  assert.equal(done.events[1]?.type, "message.delta");
  if (done.events[0]?.type === "message.delta" && done.events[1]?.type === "message.delta") {
    assert.equal(`${done.events[0].delta}${done.events[1].delta}`, "provider:mock");
  }
});

test("completion events carry the mock provider metadata", () => {
  const event = parseRunEvent({
    type: "message.completed",
    request_id: REQUEST,
    run_id: RUN,
    organization_id: ORG,
    message: "mock:mock-text:Hello KAI",
    model_id: "mock-text",
    provider_id: "mock",
    verified: true,
  });
  assert.equal(event.type, "message.completed");
  if (event.type === "message.completed") {
    assert.equal(event.provider_id, "mock");
    assert.equal(event.model_id, "mock-text");
    assert.equal(event.verified, true);
  }
});

test("run.failed keeps only the public error fields", () => {
  const event = parseRunEvent({
    type: "run.failed",
    request_id: REQUEST,
    run_id: RUN,
    organization_id: ORG,
    error: {
      kind: "provider_unavailable",
      stage: "model_selection",
      request_id: REQUEST,
      run_id: RUN,
      organization_id: ORG,
      message: "The model provider is unavailable. Stage: model_selection.",
      traceback: "secret",
    },
  });
  assert.equal(event.type, "run.failed");
  if (event.type === "run.failed") {
    assert.equal(event.error.kind, "provider_unavailable");
    assert.equal("traceback" in event.error, false);
  }
});

test("a malformed event does not surface the payload", () => {
  assert.throws(() => parseRunEvent({ type: "message.delta", delta: "sk-live-secret" }), ChatContractError);
  try {
    parseRunEvent({ type: "message.delta", delta: "sk-live-secret" });
  } catch (error) {
    assert.equal(error instanceof Error && error.message.includes("sk-live"), false);
  }
});

test("readChatRequest rejects an organization id and an empty message", () => {
  assert.throws(
    () => readChatRequest({ message: "Hello", conversation_id: CONVERSATION, organization_id: ORG }),
    ChatRequestError,
  );
  assert.throws(() => readChatRequest({ message: "", conversation_id: CONVERSATION }), ChatRequestError);
  const accepted = readChatRequest({ message: "Hello KAI", conversation_id: CONVERSATION });
  assert.equal(accepted.message, "Hello KAI");
});
