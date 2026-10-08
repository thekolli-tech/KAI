"use client";

import { useRouter } from "next/navigation";

import { useChat } from "@/components/chat/chat-provider";
import { EmptyState } from "@/components/kai/empty-state";
import { ErrorState } from "@/components/kai/error-state";
import { Button } from "@/components/ui/button";

export function ConversationList() {
  const { state, newChat, openConversation } = useChat();
  const router = useRouter();
  const busy = state.status === "submitting" || state.status === "streaming";

  async function start() {
    await newChat();
    router.push("/");
  }

  async function open(id: string) {
    await openConversation(id);
    router.push("/");
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-5 py-10 md:px-8">
      <header className="flex items-center justify-between gap-3">
        <h1 className="font-display text-4xl">Chats</h1>
        <Button type="button" variant="outline" disabled={busy} onClick={() => void start()}>
          New chat
        </Button>
      </header>
      {state.notice !== null ? <ErrorState title="Chats are unavailable" detail={state.notice} /> : null}
      {state.conversations.length === 0 ? (
        <EmptyState
          title="No conversations yet"
          detail="Start a chat from the composer. The transcript is saved for this organization."
        />
      ) : (
        <ul className="grid gap-2">
          {state.conversations.map((conversation) => (
            <li key={conversation.id}>
              <button
                type="button"
                disabled={busy}
                onClick={() => void open(conversation.id)}
                className="flex w-full items-center justify-between rounded-2xl border border-border bg-card/40 px-4 py-3 text-left hover:border-gold/40"
              >
                <span className="text-sm text-foreground">{conversation.title}</span>
                <span className="text-[11px] tracking-[0.14em] text-silver uppercase">
                  {conversation.id === state.activeConversationId ? "Open" : "Saved here"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
