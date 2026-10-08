type FileAttachmentProps = {
  name: string;
  mediaType: string;
  byteSize: number;
};

export function FileAttachment({ name, mediaType, byteSize }: FileAttachmentProps) {
  return (
    <div className="inline-flex max-w-full items-center gap-3 rounded-xl border border-border bg-card px-3 py-2">
      <span className="truncate text-sm text-foreground">{name}</span>
      <span className="shrink-0 text-xs text-silver">
        {mediaType} · {formatBytes(byteSize)}
      </span>
    </div>
  );
}

function formatBytes(byteSize: number): string {
  if (byteSize < 1024) {
    return `${byteSize} B`;
  }
  if (byteSize < 1024 * 1024) {
    return `${(byteSize / 1024).toFixed(1)} KB`;
  }
  return `${(byteSize / (1024 * 1024)).toFixed(1)} MB`;
}
