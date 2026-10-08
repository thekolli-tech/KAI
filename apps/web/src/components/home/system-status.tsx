"use client";

import type { HealthReport } from "@kai/types";

import { AgentStatus } from "@/components/kai/agent-status";
import { ChatMessage } from "@/components/kai/chat-message";
import { ErrorState } from "@/components/kai/error-state";
import { LoadingState } from "@/components/kai/loading-state";
import { ToolCall } from "@/components/kai/tool-call";
import { checkEntries, checkLabel, describeCheck, statusMessage } from "@/lib/health-summary";
import { useHealth } from "@/lib/use-health";

export function SystemStatus() {
  const { view, reload } = useHealth();

  if (view.status === "loading") {
    return <LoadingState label="Checking the KAI API" />;
  }

  if (view.status === "error") {
    return (
      <ErrorState
        title="KAI API is unreachable"
        detail={view.detail}
        onRetry={reload}
      />
    );
  }

  return <ReadyStatus report={view.report} />;
}

function ReadyStatus({ report }: { report: HealthReport }) {
  return (
    <section className="grid gap-4" aria-label="System status">
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs tracking-wide text-silver">
        <p>
          <span className="text-gold">Model</span>
          <span className="mx-2 text-border">/</span>
          {describeCheck(report.checks.model_runtime)}
        </p>
        <p>
          <span className="text-gold">Phase</span>
          <span className="mx-2 text-border">/</span>
          {report.phase}
        </p>
      </div>
      <ChatMessage role="system" content={statusMessage(report)} />
      <ToolCall
        name="none"
        state="idle"
        detail="No tool has been selected. The tool catalog is not executable."
      />
      <AgentStatus
        name="KAI Engine"
        state="idle"
        detail="Stage interfaces are defined. The pipeline does not run in this phase."
      />
      <dl className="grid gap-2 sm:grid-cols-2">
        {checkEntries(report).map(({ key, state }) => (
          <div key={key} className="flex items-center justify-between rounded-xl border border-border/70 px-3 py-2">
            <dt className="text-sm text-foreground">{checkLabel(key)}</dt>
            <dd className="text-xs text-silver">{describeCheck(state)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
