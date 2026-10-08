"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { primaryNav, settingsNav } from "@/lib/navigation";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-[4.75rem] shrink-0 flex-col border-r border-sidebar-border bg-sidebar pt-3 md:w-60">
      <nav className="flex flex-1 flex-col gap-1 px-2" aria-label="Workspace">
        {primaryNav.map((item) => (
          <NavLink key={item.href} href={item.href} label={item.label} active={isActive(pathname, item.href)}>
            <item.icon />
          </NavLink>
        ))}
      </nav>
      <div className="px-2 pb-4">
        <NavLink
          href={settingsNav.href}
          label={settingsNav.label}
          active={isActive(pathname, settingsNav.href)}
        >
          <settingsNav.icon />
        </NavLink>
      </div>
    </aside>
  );
}

function isActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavLink({
  href,
  label,
  active,
  children,
}: {
  href: string;
  label: string;
  active: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      title={label}
      className={cn(
        "flex h-10 items-center gap-3 rounded-xl px-3 text-sm text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        active && "bg-sidebar-accent text-gold",
      )}
    >
      {children}
      <span className="sr-only md:not-sr-only">{label}</span>
    </Link>
  );
}
