export function apiOrigin(): string {
  const configured = process.env.KAI_API_ORIGIN?.trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }
  return "http://127.0.0.1:8000";
}

export function localBearerToken(): string {
  return process.env.KAI_LOCAL_BEARER_TOKEN?.trim() ?? "";
}

export function chatStreamUrl(): string {
  return `${apiOrigin()}/api/v1/chat/stream`;
}
