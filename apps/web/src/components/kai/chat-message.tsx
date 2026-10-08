import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";

import { CodeBlock } from "@/components/kai/code-block";

type ChatRole = "user" | "assistant" | "system";

type ChatMessageProps = {
  role: ChatRole;
  content: string;
  modelLabel?: string;
  streaming?: boolean;
};

const roleLabels: Record<ChatRole, string> = {
  user: "You",
  assistant: "KAI",
  system: "Status",
};

export function ChatMessage({ role, content, modelLabel, streaming = false }: ChatMessageProps) {
  return (
    <article className="grid gap-2">
      <header className="flex items-baseline justify-between gap-3 text-[11px] tracking-[0.16em] text-silver uppercase">
        <span>{roleLabels[role]}</span>
        {role === "assistant" ? (
          <span className="flex items-center gap-2">
            <span>{modelLabel ?? "Development Model"}</span>
            {streaming ? <span className="text-gold">Streaming</span> : null}
          </span>
        ) : null}
      </header>
      <div className="kai-markdown text-sm leading-6 text-foreground/90">
        <ReactMarkdown
          components={{
            code({ className, children }) {
              return renderCode(className, children);
            },
            pre({ children }) {
              return <>{children}</>;
            },
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </article>
  );
}

function renderCode(className: string | undefined, children: ReactNode) {
  const text = String(children).replace(/\n$/, "");
  const language = /language-([\w-]+)/.exec(className ?? "")?.[1];
  if (!language) {
    return <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">{text}</code>;
  }
  return <CodeBlock code={text} language={language} />;
}
