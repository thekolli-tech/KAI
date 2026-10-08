"use client";

import { brand } from "@kai/shared";

import { useChat } from "@/components/chat/chat-provider";
import { Transcript } from "@/components/chat/transcript";
import { QuickActions } from "@/components/home/quick-actions";
import { SystemStatus } from "@/components/home/system-status";
import { Button } from "@/components/ui/button";

export function WorkspaceHome() {
  const { state, newChat } = useChat();
  const chatting = state.messages.length > 0;
  const busy = state.status === "submitting" || state.status === "streaming";

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-10 px-5 py-10 md:px-8 md:py-14">
      <header className="grid gap-4">
        <p className="text-[11px] tracking-[0.28em] text-gold uppercase">{brand.maker}</p>
        <h1
          className={
            chatting
              ? "font-display text-4xl leading-none text-foreground"
              : "font-display text-6xl leading-none text-foreground md:text-7xl"
          }
        >
          {brand.name}
        </h1>
        <p className="max-w-lg text-lg text-silver">{brand.tagline}</p>
        {chatting ? null : <p className="font-display text-3xl text-foreground/90">{brand.prompt}</p>}
        <div>
          <Button type="button" variant="outline" disabled={busy} onClick={() => void newChat()}>
            New chat
          </Button>
        </div>
      </header>
      <Transcript />
      {chatting ? null : <QuickActions />}
      <SystemStatus />
    </div>
  );
}
