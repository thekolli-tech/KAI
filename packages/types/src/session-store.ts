import type { ConversationDetail, ConversationMessage, ConversationSummary } from "./chat";

const TITLE_LIMIT = 48;

export type SessionStore = {
  create(): ConversationDetail;
  list(): ConversationSummary[];
  get(id: string): ConversationDetail | undefined;
  appendUser(conversationId: string, content: string): ConversationMessage | undefined;
  beginAssistant(conversationId: string): ConversationMessage | undefined;
  patchAssistant(
    conversationId: string,
    messageId: string,
    patch: Partial<Pick<ConversationMessage, "content" | "status" | "providerLabel" | "error">>,
  ): void;
};

export function createSessionStore(): SessionStore {
  const conversations = new Map<string, ConversationDetail>();

  function touch(conversation: ConversationDetail, title?: string): void {
    conversation.updatedAt = new Date().toISOString();
    if (title !== undefined) {
      conversation.title = title;
    }
  }

  return {
    create() {
      const now = new Date().toISOString();
      const conversation: ConversationDetail = {
        id: crypto.randomUUID(),
        title: "New chat",
        updatedAt: now,
        messages: [],
      };
      conversations.set(conversation.id, conversation);
      return conversation;
    },
    list() {
      return [...conversations.values()]
        .map(({ id, title, updatedAt }) => ({ id, title, updatedAt }))
        .sort((left, right) => (left.updatedAt < right.updatedAt ? 1 : -1));
    },
    get(id) {
      const conversation = conversations.get(id);
      if (conversation === undefined) {
        return undefined;
      }
      return {
        ...conversation,
        messages: conversation.messages.map((message) => ({ ...message })),
      };
    },
    appendUser(conversationId, content) {
      const conversation = conversations.get(conversationId);
      if (conversation === undefined) {
        return undefined;
      }
      const message: ConversationMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content,
        status: "completed",
        providerLabel: null,
        error: null,
      };
      conversation.messages.push(message);
      const title = conversation.title === "New chat" ? content.slice(0, TITLE_LIMIT) : undefined;
      touch(conversation, title);
      return message;
    },
    beginAssistant(conversationId) {
      const conversation = conversations.get(conversationId);
      if (conversation === undefined) {
        return undefined;
      }
      const message: ConversationMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "",
        status: "streaming",
        providerLabel: null,
        error: null,
      };
      conversation.messages.push(message);
      touch(conversation);
      return message;
    },
    patchAssistant(conversationId, messageId, patch) {
      const conversation = conversations.get(conversationId);
      const message = conversation?.messages.find((item) => item.id === messageId);
      if (conversation === undefined || message === undefined || message.role !== "assistant") {
        return;
      }
      if (message.status !== "streaming") {
        return;
      }
      if (patch.content !== undefined) {
        message.content = patch.content;
      }
      if (patch.providerLabel !== undefined) {
        message.providerLabel = patch.providerLabel;
      }
      if (patch.error !== undefined) {
        message.error = patch.error;
      }
      if (patch.status !== undefined) {
        message.status = patch.status;
      }
      touch(conversation);
    },
  };
}
