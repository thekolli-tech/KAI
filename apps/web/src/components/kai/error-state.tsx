import { Button } from "@/components/ui/button";

type ErrorStateProps = {
  title: string;
  detail: string;
  onRetry?: () => void;
};

export function ErrorState({ title, detail, onRetry }: ErrorStateProps) {
  return (
    <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-4" role="alert">
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
      {onRetry ? (
        <Button className="mt-3" variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}
