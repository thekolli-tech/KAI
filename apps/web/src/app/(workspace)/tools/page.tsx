import { ReservedSurface } from "@/components/layout/reserved-surface";
import { surfaces } from "@/lib/surfaces";

export default function ToolsPage() {
  return <ReservedSurface {...surfaces.tools} />;
}
