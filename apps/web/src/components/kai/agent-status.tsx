type AgentState = "idle" | "running" | "unavailable";

type AgentStatusProps = {
  name: string;
  state: AgentState;
  detail: string;
};

const stateLabels: Record<AgentState, string> = {
  idle: "Idle",
  running: "Running",
  unavailable: "Unavailable",
};

export function AgentStatus({ name, state, detail }: AgentStatusProps) {
  return (
    <div className="rounded-xl border border-border px-3 py-2">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-foreground">{name}</p>
        <p className="text-[11px] tracking-[0.14em] text-gold uppercase">{stateLabels[state]}</p>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
    </div>
  );
}
