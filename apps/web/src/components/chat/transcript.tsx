"use client";

import { mockRuntimeNote, providerLabel } from "@kai/types";
import { useEffect, useRef } from "react";

import { useChat } from "@/components/chat/chat-provider";
import { ChatMessage } from "@/components/kai/chat-message";
import { ErrorState } from "@/components/kai/error-state";

export function Transcript() {
  const { state, retry } = useChat();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [state.messages, state.status]);

  if (state.messages.length === 0 && state.notice === null) {
    return null;
  }

  return (
    <section className="grid gap-6" aria-live="polite" aria-label="Conversation">
      {state.notice !== null && state.messages.length === 0 ? (
        <ErrorState title="The message was not sent" detail={state.notice} />
      ) : null}
      <ol className="grid gap-6">
        {state.messages.map((message, index) => {
          const isLast = index === state.messages.length - 1;
          return (
            <li key={message.id}>
              <ChatMessage
                role={message.role}
                content={message.content}
                modelLabel={
                  message.role === "assistant"
                    ? (message.providerLabel ?? providerLabel("mock"))
                    : undefined
                }
                streaming={message.status === "streaming"}
              />
              {message.role === "assistant" ? (
                <p className="mt-1 text-[11px] tracking-[0.14em] text-muted-foreground uppercase">
                  {mockRuntimeNote}
                </p>
              ) : null}
              {message.status === "cancelled" ? (
                <p className="mt-2 text-xs text-muted-foreground">Stopped</p>
              ) : null}
              {message.status === "failed" && message.error !== null ? (
                <div className="mt-3">
                  <ErrorState
                    title="The reply failed"
                    detail={message.error}
                    onRetry={isLast ? () => void retry() : undefined}
                  />
                </div>
              ) : null}
            </li>
          );
        })}
      </ol>
      <div ref={endRef} />
    </section>
  );
}
