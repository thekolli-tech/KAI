"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";

type CodeBlockProps = {
  code: string;
  language?: string;
};

export function CodeBlock({ code, language }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <figure className="overflow-hidden rounded-xl border border-border bg-background/70">
      <figcaption className="flex items-center justify-between border-b border-border px-3 py-1.5 text-[11px] tracking-wide text-silver uppercase">
        <span>{language ?? "text"}</span>
        <Button variant="ghost" size="xs" onClick={() => void copy()}>
          {copied ? "Copied" : "Copy"}
        </Button>
      </figcaption>
      <pre className="overflow-x-auto p-3 font-mono text-xs leading-5 text-foreground">
        <code>{code}</code>
      </pre>
    </figure>
  );
}
