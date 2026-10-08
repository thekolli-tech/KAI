import { quickActions } from "@kai/shared";

export function QuickActions() {
  return (
    <div>
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {quickActions.map((action) => (
          <li key={action.id}>
            <button
              type="button"
              disabled
              title={`${action.label} is not available in this phase`}
              className="flex h-20 w-full flex-col items-start justify-between rounded-2xl border border-border bg-card/40 px-3 py-3 text-left opacity-80"
            >
              <span className="text-sm text-foreground">{action.label}</span>
              <span className="text-[11px] tracking-[0.16em] text-gold uppercase">Planned</span>
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted-foreground">
        These actions are reserved. They do not call a model, tool, or agent.
      </p>
    </div>
  );
}
