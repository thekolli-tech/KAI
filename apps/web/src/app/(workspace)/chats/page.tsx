import { ReservedSurface } from "@/components/layout/reserved-surface";
import { surfaces } from "@/lib/surfaces";

export default function ChatsPage() {
  return <ReservedSurface {...surfaces.chats} />;
}
