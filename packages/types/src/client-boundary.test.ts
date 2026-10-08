import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const WEB_SRC = path.resolve(import.meta.dirname, "../../../apps/web/src");

const TOKEN_FILES = new Set([path.normalize("server/upstream.ts"), path.normalize("app/api/chat/stream/route.ts")]);

const UPSTREAM_FILES = new Set([path.normalize("server/upstream.ts")]);

test("client source does not carry credentials or provider internals", () => {
  const offenders: string[] = [];
  for (const file of walk(WEB_SRC)) {
    const relative = path.normalize(path.relative(WEB_SRC, file));
    const text = readFileSync(file, "utf8");
    if (text.includes("KAI_LOCAL_BEARER_TOKEN") && !TOKEN_FILES.has(relative)) {
      offenders.push(`${relative}: bearer env`);
    }
    if (text.includes("/api/v1/chat") && !UPSTREAM_FILES.has(relative)) {
      offenders.push(`${relative}: direct chat route`);
    }
    if (/NEXT_PUBLIC_[A-Z0-9_]*(TOKEN|SECRET|KEY|BEARER|PASSWORD)/.test(text)) {
      offenders.push(`${relative}: public secret`);
    }
    for (const banned of [
      "localStorage",
      "sessionStorage",
      "createSessionStore",
      "MockModelProvider",
      "ProviderRegistry",
      "KaiEngine",
      "openai",
      "anthropic",
      "generative-ai",
      "perplexity",
    ]) {
      if (text.includes(banned)) {
        offenders.push(`${relative}: ${banned}`);
      }
    }
  }
  assert.deepEqual(offenders, []);
});

function walk(directory: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(directory)) {
    const full = path.join(directory, entry);
    if (statSync(full).isDirectory()) {
      files.push(...walk(full));
    } else if (full.endsWith(".ts") || full.endsWith(".tsx")) {
      files.push(full);
    }
  }
  return files;
}
