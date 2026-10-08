const PUBLIC_SENTENCES = new Set([
  "Authentication is required.",
  "The message is not valid.",
  "The request could not be completed.",
  "The organization boundary refused the request.",
  "That conversation is not available.",
  "The request is invalid.",
  "A required dependency is unavailable.",
  "The stage failed.",
  "The model provider is unavailable.",
  "Execution failed.",
  "Verification rejected the result.",
  "The run was cancelled.",
]);

const STAGE_SUFFIX = / Stage: [a-z_]+\.$/;
const UNSAFE_TEXT =
  /traceback|bearer|sk-|postgres|password|secret|KAI_LOCAL|\/[A-Za-z0-9_./-]+\.py|\\/i;

export function displayError(input: { status?: number; message?: string }): string {
  if (input.status === 401) {
    return "Authentication is required.";
  }
  if (input.status === 422) {
    return "The message is not valid.";
  }
  if (input.status === 403) {
    return "The organization boundary refused the request.";
  }
  if (input.status === 404) {
    return "That conversation is not available.";
  }
  const message = input.message?.trim() ?? "";
  if (message !== "" && isPublicMessage(message)) {
    return message;
  }
  return "The request could not be completed.";
}

function isPublicMessage(message: string): boolean {
  if (message.length > 200 || UNSAFE_TEXT.test(message)) {
    return false;
  }
  const sentence = message.replace(STAGE_SUFFIX, "");
  return PUBLIC_SENTENCES.has(sentence);
}
