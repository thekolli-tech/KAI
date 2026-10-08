import assert from "node:assert/strict";
import test from "node:test";

import { createSessionStore } from "./session-store.ts";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

test("conversation ids are created by the store", () => {
  const store = createSessionStore();
  const created = store.create();
  assert.match(created.id, UUID_PATTERN);
  assert.equal(created.title, "New chat");
  const user = store.appendUser(created.id, "Hello KAI");
  const assistant = store.beginAssistant(created.id);
  assert.ok(user);
  assert.ok(assistant);
  assert.match(user.id, UUID_PATTERN);
  assert.notEqual(user.id, created.id);
  store.patchAssistant(created.id, assistant.id, {
    content: "mock:mock-text:Hello KAI",
    status: "completed",
    providerLabel: "Local Mock Provider",
  });
  const loaded = store.get(created.id);
  assert.equal(loaded?.title, "Hello KAI");
  assert.equal(loaded?.messages[1]?.content, "mock:mock-text:Hello KAI");
  assert.equal(loaded?.messages[1]?.providerLabel, "Local Mock Provider");
  store.patchAssistant(created.id, assistant.id, { content: "changed" });
  assert.equal(store.get(created.id)?.messages[1]?.content, "mock:mock-text:Hello KAI");
});
