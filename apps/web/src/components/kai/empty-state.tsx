type EmptyStateProps = {
  title: string;
  detail: string;
};

export function EmptyState({ title, detail }: EmptyStateProps) {
  return (
    <div className="max-w-md text-center">
      <p className="font-display text-3xl text-foreground">{title}</p>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}
