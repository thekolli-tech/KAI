import { EmptyState } from "@/components/kai/empty-state";

export function ReservedSurface({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="flex min-h-full items-center justify-center px-6 py-16">
      <EmptyState title={title} detail={detail} />
    </div>
  );
}
