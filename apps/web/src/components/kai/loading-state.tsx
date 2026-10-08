type LoadingStateProps = {
  label?: string;
};

export function LoadingState({ label = "Loading" }: LoadingStateProps) {
  return (
    <div className="flex items-center gap-3 text-sm text-muted-foreground" role="status">
      <span className="relative h-px w-10 overflow-hidden bg-border">
        <span className="absolute inset-y-0 left-0 w-1/2 animate-pulse bg-gold" />
      </span>
      {label}
    </div>
  );
}
