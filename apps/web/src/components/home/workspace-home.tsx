import { brand } from "@kai/shared";

import { QuickActions } from "@/components/home/quick-actions";
import { SystemStatus } from "@/components/home/system-status";

export function WorkspaceHome() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-10 px-5 py-10 md:px-8 md:py-14">
      <header className="grid gap-4">
        <p className="text-[11px] tracking-[0.28em] text-gold uppercase">{brand.maker}</p>
        <h1 className="font-display text-6xl leading-none text-foreground md:text-7xl">{brand.name}</h1>
        <p className="max-w-lg text-lg text-silver">{brand.tagline}</p>
        <p className="font-display text-3xl text-foreground/90">{brand.prompt}</p>
      </header>
      <QuickActions />
      <SystemStatus />
    </div>
  );
}
