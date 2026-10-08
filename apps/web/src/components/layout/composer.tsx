import { Input } from "@/components/ui/input";

export function Composer() {
  return (
    <div className="border-t border-border bg-background/80 px-4 py-3 backdrop-blur-md md:px-6">
      <label htmlFor="kai-composer" className="sr-only">
        Message
      </label>
      <Input
        id="kai-composer"
        disabled
        placeholder="Ask KAI anything..."
        aria-describedby="composer-note"
      />
      <p id="composer-note" className="mt-2 text-xs text-muted-foreground">
        The chat API is not connected. This field does not send a message.
      </p>
    </div>
  );
}
