import assert from "node:assert/strict";
import test from "node:test";

import { chatReducer, initialChatState, type ChatViewState } from "./chat-state.ts";
import type { RunEvent } from "./chat.ts";
import { displayError } from "./public-error.ts";
import { providerLabel } from "./provider-label.ts";

const REQUEST = "33333333-3333-4333-8333-333333333333";
const RUN = "44444444-4444-4444-8444-444444444444";
const ORG = "22222222-2222-4222-8222-222222222222";
const CONVERSATION = "55555555-5555-4555-8555-555555555555";

function started(): ChatViewState {
  return chatReducer(initialChatState, {
    type: "start-turn",
    conversation: { id: CONVERSATION, title: "New chat", updatedAt: "2026-10-08T00:00:00.000Z" },
    userId: "66666666-6666-4666-8666-666666666666",
    assistantId: "77777777-7777-4777-8777-777777777777",
    text: "Hello KAI",
  });
}

function apply(state: ChatViewState, event: RunEvent): ChatViewState {
  return chatReducer(state, { type: "event", event });
}

function correlation() {
  return { request_id: REQUEST, run_id: RUN, organization_id: ORG };
}

test("chat submission shows the user message and locks a second submit", () => {
  const state = started();
  assert.equal(state.status, "submitting");
  assert.equal(state.messages[0]?.content, "Hello KAI");
  assert.equal(state.messages[0]?.role, "user");
  assert.equal(state.messages[1]?.role, "assistant");
  assert.equal(state.messages[1]?.content, "");
  const duplicate = chatReducer(state, {
    type: "start-turn",
    conversation: { id: CONVERSATION, title: "Hello KAI", updatedAt: "2026-10-08T00:00:00.000Z" },
    userId: "88888888-8888-4888-8888-888888888888",
    assistantId: "99999999-9999-4999-8999-999999999999",
    text: "again",
  });
  assert.equal(duplicate, state);
});

test("deltas reconstruct the assistant message before the run completes", () => {
  let state = apply(started(), { type: "run.started", ...correlation() });
  assert.equal(state.status, "streaming");
  const deltas = ["mock:mock-text:", "Hello KAI"];
  for (const delta of deltas) {
    state = apply(state, { type: "message.delta", ...correlation(), delta });
  }
  assert.equal(state.messages[1]?.content, deltas.join(""));
  assert.equal(state.status, "streaming");
  state = apply(state, {
    type: "message.completed",
    ...correlation(),
    message: deltas.join(""),
    model_id: "mock-text",
    provider_id: "mock",
    verified: true,
  });
  assert.equal(state.messages[1]?.content, "mock:mock-text:Hello KAI");
  assert.equal(state.messages[1]?.providerLabel, "Local Mock Provider");
  assert.equal(state.messages[1]?.status, "completed");
  state = apply(state, {
    type: "run.completed",
    ...correlation(),
    message: deltas.join(""),
    model_id: "mock-text",
    provider_id: "mock",
    verified: true,
  });
  assert.equal(state.status, "completed");
});

test("run.failed displays the public message and hides secrets", () => {
  const streaming = apply(started(), { type: "run.started", ...correlation() });
  const failed = apply(streaming, {
    type: "run.failed",
    ...correlation(),
    error: {
      kind: "execution_failure",
      message: "Execution failed. Stage: model_selection.",
    },
  });
  assert.equal(failed.status, "failed");
  assert.equal(failed.messages[1]?.error, "Execution failed. Stage: model_selection.");
  const hidden = chatReducer(streaming, { type: "fail", message: "Traceback sk-live-secret /workspace/app.py" });
  assert.equal(hidden.notice, "The request could not be completed.");
  assert.equal(hidden.notice?.includes("sk-live"), false);
});

test("cancellation keeps the partial reply and does not become a failure", () => {
  let state = apply(started(), { type: "run.started", ...correlation() });
  state = apply(state, { type: "message.delta", ...correlation(), delta: "mock:" });
  state = chatReducer(state, { type: "cancel" });
  assert.equal(state.status, "cancelled");
  assert.equal(state.messages[1]?.status, "cancelled");
  assert.equal(state.messages[1]?.content, "mock:");
  assert.equal(state.notice, null);
  const after = chatReducer(state, { type: "fail", message: "The request could not be completed." });
  assert.equal(after.status, "cancelled");
});

test("http and network errors stay generic", () => {
  assert.equal(displayError({ status: 401, message: "Bearer sk-live" }), "Authentication is required.");
  assert.equal(displayError({ status: 422, message: "loc message" }), "The message is not valid.");
  assert.equal(displayError({ status: 500, message: "Traceback" }), "The request could not be completed.");
  assert.equal(displayError({ status: 0 }), "The request could not be completed.");
  assert.equal(providerLabel("mock"), "Local Mock Provider");
  assert.equal(providerLabel("openai"), "Development Model");
  assert.equal(providerLabel(null), "Development Model");
});
