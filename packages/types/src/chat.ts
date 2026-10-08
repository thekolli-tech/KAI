const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export class ChatContractError extends Error {
  constructor() {
    super("The response could not be read.");
    this.name = "ChatContractError";
  }
}

export class ChatRequestError extends Error {
  constructor() {
    super("The message is not valid.");
    this.name = "ChatRequestError";
  }
}

export class ChatHttpError extends Error {
  readonly status: number;

  constructor(status: number) {
    super("The request could not be completed.");
    this.name = "ChatHttpError";
    this.status = status;
  }
}

export type ChatRequest = {
  message: string;
  conversation_id?: string;
  project_id?: string;
  attachment_ids?: string[];
};

export type RunCorrelation = {
  request_id: string;
  run_id: string;
  organization_id: string;
};

export type RunStartedEvent = RunCorrelation & {
  type: "run.started";
};

export type MessageDeltaEvent = RunCorrelation & {
  type: "message.delta";
  delta: string;
};

export type MessageCompletedEvent = RunCorrelation & {
  type: "message.completed";
  message: string;
  model_id: string | null;
  provider_id: string | null;
  verified: boolean;
};

export type RunCompletedEvent = RunCorrelation & {
  type: "run.completed";
  message: string;
  model_id: string | null;
  provider_id: string | null;
  verified: boolean;
};

export type PublicRunError = {
  message: string;
  kind?: string;
  stage?: string;
  request_id?: string;
  run_id?: string;
  organization_id?: string;
};

export type RunFailedEvent = RunCorrelation & {
  type: "run.failed";
  error: PublicRunError;
};

export type RunEvent =
  | RunStartedEvent
  | MessageDeltaEvent
  | MessageCompletedEvent
  | RunCompletedEvent
  | RunFailedEvent;

export type ConversationMessageStatus = "streaming" | "completed" | "failed" | "cancelled";

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: ConversationMessageStatus;
  providerLabel: string | null;
  error: string | null;
};

export type ConversationSummary = {
  id: string;
  title: string;
  updatedAt: string;
};

export type ConversationDetail = ConversationSummary & {
  messages: ConversationMessage[];
};

const MESSAGE_LIMIT = 32_000;

export function readChatRequest(value: unknown): { message: string; conversation_id: string } {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new ChatRequestError();
  }
  const record = value as Record<string, unknown>;
  if ("organization_id" in record) {
    throw new ChatRequestError();
  }
  const message = record.message;
  if (typeof message !== "string" || message.length < 1 || message.length > MESSAGE_LIMIT) {
    throw new ChatRequestError();
  }
  if (!isUuid(record.conversation_id)) {
    throw new ChatRequestError();
  }
  return { message, conversation_id: record.conversation_id };
}

export function parseRunEvent(value: unknown): RunEvent {
  const record = objectRecord(value);
  const correlation = readCorrelation(record);
  switch (record.type) {
    case "run.started":
      return { type: "run.started", ...correlation };
    case "message.delta":
      if (typeof record.delta !== "string") {
        throw new ChatContractError();
      }
      return { type: "message.delta", ...correlation, delta: record.delta };
    case "message.completed":
      return { type: "message.completed", ...correlation, ...readCompletion(record) };
    case "run.completed":
      return { type: "run.completed", ...correlation, ...readCompletion(record) };
    case "run.failed":
      return { type: "run.failed", ...correlation, error: readPublicError(record.error) };
    default:
      throw new ChatContractError();
  }
}

export function takeSseEvents(buffer: string): { events: RunEvent[]; rest: string } {
  const normalized = buffer.replaceAll("\r\n", "\n");
  const parts = normalized.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: RunEvent[] = [];
  for (const part of parts) {
    const frame = part.trim();
    if (frame === "" || frame.startsWith(":")) {
      continue;
    }
    events.push(parseSseFrame(frame));
  }
  return { events, rest };
}

export function parseConversationSummary(value: unknown): ConversationSummary {
  const record = objectRecord(value);
  if (!isUuid(record.id) || typeof record.title !== "string" || record.title.length < 1) {
    throw new ChatContractError();
  }
  if (typeof record.updatedAt !== "string" || record.updatedAt.length < 1) {
    throw new ChatContractError();
  }
  return { id: record.id, title: record.title, updatedAt: record.updatedAt };
}

export function parseConversationDetail(value: unknown): ConversationDetail {
  const summary = parseConversationSummary(value);
  const record = objectRecord(value);
  if (!Array.isArray(record.messages)) {
    throw new ChatContractError();
  }
  return { ...summary, messages: record.messages.map(parseConversationMessage) };
}

export function parseConversationList(value: unknown): ConversationSummary[] {
  const record = objectRecord(value);
  if (!Array.isArray(record.conversations)) {
    throw new ChatContractError();
  }
  return record.conversations.map(parseConversationSummary);
}

function parseSseFrame(frame: string): RunEvent {
  let eventName = "";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }
  if (eventName === "" || dataLines.length === 0) {
    throw new ChatContractError();
  }
  let payload: unknown;
  try {
    payload = JSON.parse(dataLines.join("\n"));
  } catch {
    throw new ChatContractError();
  }
  const event = parseRunEvent(payload);
  if (event.type !== eventName) {
    throw new ChatContractError();
  }
  return event;
}

function parseConversationMessage(value: unknown): ConversationMessage {
  const record = objectRecord(value);
  if (!isUuid(record.id) || (record.role !== "user" && record.role !== "assistant")) {
    throw new ChatContractError();
  }
  if (typeof record.content !== "string") {
    throw new ChatContractError();
  }
  if (!isMessageStatus(record.status)) {
    throw new ChatContractError();
  }
  return {
    id: record.id,
    role: record.role,
    content: record.content,
    status: record.status,
    providerLabel: nullableString(record.providerLabel),
    error: nullableString(record.error),
  };
}

function readCorrelation(record: Record<string, unknown>): RunCorrelation {
  if (!isUuid(record.request_id) || !isUuid(record.run_id) || !isUuid(record.organization_id)) {
    throw new ChatContractError();
  }
  return {
    request_id: record.request_id,
    run_id: record.run_id,
    organization_id: record.organization_id,
  };
}

function readCompletion(record: Record<string, unknown>): {
  message: string;
  model_id: string | null;
  provider_id: string | null;
  verified: boolean;
} {
  if (typeof record.message !== "string" || typeof record.verified !== "boolean") {
    throw new ChatContractError();
  }
  return {
    message: record.message,
    model_id: nullableString(record.model_id),
    provider_id: nullableString(record.provider_id),
    verified: record.verified,
  };
}

function readPublicError(value: unknown): PublicRunError {
  const record = objectRecord(value);
  if (typeof record.message !== "string" || record.message.length < 1 || record.message.length > 500) {
    throw new ChatContractError();
  }
  const error: PublicRunError = { message: record.message };
  for (const key of ["kind", "stage", "request_id", "run_id", "organization_id"] as const) {
    const item = record[key];
    if (item === undefined) {
      continue;
    }
    if (typeof item !== "string") {
      throw new ChatContractError();
    }
    error[key] = item;
  }
  return error;
}

function nullableString(value: unknown): string | null {
  if (value === undefined || value === null) {
    return null;
  }
  if (typeof value !== "string") {
    throw new ChatContractError();
  }
  return value;
}

function isMessageStatus(value: unknown): value is ConversationMessageStatus {
  return value === "streaming" || value === "completed" || value === "failed" || value === "cancelled";
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function objectRecord(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new ChatContractError();
  }
  return value as Record<string, unknown>;
}
