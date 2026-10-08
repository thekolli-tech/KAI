"use client";

import { mockRuntimeNote, providerLabel } from "@kai/types";
import { useState, type FormEvent } from "react";

import { useChat } from "@/components/chat/chat-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function Composer() {
  const { state, send, stop } = useChat();
  const [draft, setDraft] = useState("");
  const busy = state.status === "submitting" || state.status === "streaming";

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || draft.length < 1) {
      return;
    }
    const text = draft;
    setDraft("");
    void send(text);
  }

  return (
    <div className="border-t border-border bg-background/80 px-4 py-3 backdrop-blur-md md:px-6">
      <form onSubmit={onSubmit} className="flex items-center gap-2">
        <label htmlFor="kai-composer" className="sr-only">
          Message
        </label>
        <Input
          id="kai-composer"
          value={draft}
          disabled={busy}
          maxLength={32_000}
          placeholder="Ask KAI anything..."
          aria-describedby="composer-note"
          onChange={(event) => setDraft(event.target.value)}
        />
        {busy ? (
          <Button type="button" variant="outline" onClick={stop}>
            Stop generation
          </Button>
        ) : (
          <Button type="submit" disabled={draft.length < 1}>
            Send
          </Button>
        )}
      </form>
      <p id="composer-note" className="mt-2 text-xs text-muted-foreground">
        {providerLabel("mock")}. {mockRuntimeNote} This workspace process keeps the transcript.
        It is not written to the database.
      </p>
    </div>
  );
}
