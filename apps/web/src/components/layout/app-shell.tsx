import type { ReactNode } from "react";

import { ChatProvider } from "@/components/chat/chat-provider";
import { Composer } from "@/components/layout/composer";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <ChatProvider>
      <div className="flex h-dvh flex-col">
        <Topbar />
        <div className="flex min-h-0 flex-1">
          <Sidebar />
          <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
        </div>
        <Composer />
      </div>
    </ChatProvider>
  );
}
