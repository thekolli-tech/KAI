export const mockRuntimeNote = "Mock runtime. This is not a production model.";

export function providerLabel(providerId: string | null | undefined): string {
  if (providerId === "mock") {
    return "Local Mock Provider";
  }
  return "Development Model";
}
