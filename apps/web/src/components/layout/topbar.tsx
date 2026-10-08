"use client";

import { brand } from "@kai/shared";

import { Dropdown } from "@/components/kai/dropdown";

export function Topbar() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-border px-4 md:px-6">
      <div>
        <p className="font-display text-2xl leading-none text-foreground">{brand.name}</p>
        <p className="text-[10px] tracking-[0.22em] text-silver uppercase">{brand.maker}</p>
      </div>
      <Dropdown
        label="Profile"
        items={[
          { id: "session", label: "No session — accounts are not enabled", disabled: true },
          { id: "settings", label: "Settings", href: "/settings" },
        ]}
      />
    </header>
  );
}
