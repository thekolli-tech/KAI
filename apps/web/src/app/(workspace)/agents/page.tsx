import { ReservedSurface } from "@/components/layout/reserved-surface";
import { surfaces } from "@/lib/surfaces";

export default function AgentsPage() {
  return <ReservedSurface {...surfaces.agents} />;
}
