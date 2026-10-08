import type { ConversationDetail, ConversationSummary, RunEvent } from "./chat";
import { providerLabel } from "./provider-label";
import { displayError } from "./public-error";

export type RequestStatus = "idle" | "submitting" | "streaming" | "completed" | "failed" | "cancelled";

export type ViewMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: "completed" | "streaming" | "failed" | "cancelled";
  providerLabel: string | null;
  error: string | null;
};

export type ChatViewState = {
  status: RequestStatus;
  activeConversationId: string | null;
  conversations: ConversationSummary[];
  messages: ViewMessage[];
  notice: string | null;
};

export type ChatAction =
  | { type: "list"; conversations: ConversationSummary[] }
  | { type: "show"; detail: ConversationDetail }
  | {
      type: "start-turn";
      conversation: ConversationSummary;
      userId: string;
      assistantId: string;
      text: string;
    }
  | { type: "event"; event: RunEvent }
  | { type: "fail"; message: string }
  | { type: "cancel" }
  | { type: "stream-end" }
  | { type: "notice"; notice: string };

export const initialChatState: ChatViewState = {
  status: "idle",
  activeConversationId: null,
  conversations: [],
  messages: [],
  notice: null,
};

export function canSubmit(state: ChatViewState): boolean {
  return state.status !== "submitting" && state.status !== "streaming";
}

export function lastUserText(state: ChatViewState): string | null {
  for (let index = state.messages.length - 1; index >= 0; index -= 1) {
    const message = state.messages[index];
    if (message?.role === "user") {
      return message.content;
    }
  }
  return null;
}

export function chatReducer(state: ChatViewState, action: ChatAction): ChatViewState {
  switch (action.type) {
    case "list":
      return { ...state, conversations: action.conversations };
    case "show":
      return showConversation(state, action.detail);
    case "start-turn":
      return startTurn(state, action);
    case "event":
      return applyRunEvent(state, action.event);
    case "fail":
      return failRequest(state, action.message);
    case "cancel":
      return cancelRequest(state);
    case "stream-end":
      if (state.status === "submitting" || state.status === "streaming") {
        return failRequest(state, displayError({}));
      }
      return state;
    case "notice":
      return { ...state, notice: action.notice };
    default:
      return state;
  }
}

function startTurn(
  state: ChatViewState,
  action: Extract<ChatAction, { type: "start-turn" }>,
): ChatViewState {
  if (!canSubmit(state)) {
    return state;
  }
  const title =
    action.conversation.title === "New chat" ? action.text.slice(0, 48) : action.conversation.title;
  const summary = { ...action.conversation, title };
  const rest = state.conversations.filter((item) => item.id !== summary.id);
  return {
    ...state,
    status: "submitting",
    notice: null,
    activeConversationId: summary.id,
    conversations: [summary, ...rest],
    messages: [
      ...state.messages,
      {
        id: action.userId,
        role: "user",
        content: action.text,
        status: "completed",
        providerLabel: null,
        error: null,
      },
      {
        id: action.assistantId,
        role: "assistant",
        content: "",
        status: "streaming",
        providerLabel: null,
        error: null,
      },
    ],
  };
}

function showConversation(state: ChatViewState, detail: ConversationDetail): ChatViewState {
  if (!canSubmit(state)) {
    return state;
  }
  const summary = { id: detail.id, title: detail.title, updatedAt: detail.updatedAt };
  const rest = state.conversations.filter((item) => item.id !== detail.id);
  return {
    ...state,
    status: "idle",
    notice: null,
    activeConversationId: detail.id,
    conversations: [summary, ...rest],
    messages: detail.messages.map((message) => ({ ...message })),
  };
}

function applyRunEvent(state: ChatViewState, event: RunEvent): ChatViewState {
  if (state.status === "cancelled" || state.status === "failed" || state.status === "completed") {
    return state;
  }
  switch (event.type) {
    case "run.started":
      if (state.status !== "submitting" && state.status !== "streaming") {
        return state;
      }
      return { ...state, status: "streaming" };
    case "message.delta":
      return updateAssistant(state, (message) => ({
        ...message,
        content: `${message.content}${event.delta}`,
        status: "streaming",
      }));
    case "message.completed":
      return updateAssistant({ ...state, status: "streaming" }, (message) => ({
        ...message,
        content: event.message,
        status: "completed",
        providerLabel: providerLabel(event.provider_id),
      }));
    case "run.completed":
      return {
        ...updateAssistant(state, (message) => ({
          ...message,
          content: event.message,
          status: "completed",
          providerLabel: providerLabel(event.provider_id),
        })),
        status: "completed",
      };
    case "run.failed":
      return failRequest(state, displayError({ message: event.error.message }));
    default:
      return state;
  }
}

function failRequest(state: ChatViewState, message: string): ChatViewState {
  if (state.status === "cancelled" || state.status === "completed") {
    return state;
  }
  const safe = displayError({ message });
  return {
    ...updateAssistant(state, (item) => ({
      ...item,
      status: "failed",
      error: safe,
    })),
    status: "failed",
    notice: safe,
  };
}

function cancelRequest(state: ChatViewState): ChatViewState {
  if (state.status !== "submitting" && state.status !== "streaming") {
    return state;
  }
  return {
    ...updateAssistant(state, (message) => ({ ...message, status: "cancelled" })),
    status: "cancelled",
    notice: null,
  };
}

function updateAssistant(
  state: ChatViewState,
  update: (message: ViewMessage) => ViewMessage,
): ChatViewState {
  const index = lastAssistantIndex(state.messages);
  if (index < 0) {
    return state;
  }
  const current = state.messages[index];
  if (current === undefined || current.status === "failed" || current.status === "cancelled") {
    return state;
  }
  const messages = state.messages.slice();
  messages[index] = update(current);
  return { ...state, messages };
}

function lastAssistantIndex(messages: ViewMessage[]): number {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === "assistant") {
      return index;
    }
  }
  return -1;
}
