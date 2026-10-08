type ToolCallState = "idle" | "running" | "succeeded" | "failed";

type ToolCallProps = {
  name: string;
  state: ToolCallState;
  detail: string;
};

const stateLabels: Record<ToolCallState, string> = {
  idle: "Not run",
  running: "Running",
  succeeded: "Finished",
  failed: "Failed",
};

export function ToolCall({ name, state, detail }: ToolCallProps) {
  return (
    <div className="rounded-xl border border-border bg-card/80 px-3 py-2">
      <div className="flex items-center justify-between gap-3 text-xs tracking-wide text-silver uppercase">
        <span>Tool</span>
        <span>{stateLabels[state]}</span>
      </div>
      <p className="mt-1 font-mono text-sm text-foreground">{name}</p>
      <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
    </div>
  );
}
