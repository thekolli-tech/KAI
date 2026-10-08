import { AppShell } from "@/components/layout/app-shell";
import { ReservedSurface } from "@/components/layout/reserved-surface";

export default function NotFound() {
  return (
    <AppShell>
      <ReservedSurface
        title="This page is not part of KAI"
        detail="The workspace routes are Home, Chats, Projects, Knowledge, Agents, Tools, and Settings."
      />
    </AppShell>
  );
}
