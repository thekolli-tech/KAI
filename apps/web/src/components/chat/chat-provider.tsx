"use client";

import {
  canSubmit,
  ChatHttpError,
  chatReducer,
  createConversation,
  displayError,
  initialChatState,
  isAbortError,
  lastUserText,
  listConversations,
  loadConversation,
  streamChat,
  type ChatViewState,
} from "@kai/types";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from "react";

type ChatController = {
  state: ChatViewState;
  send: (text: string) => Promise<void>;
  stop: () => void;
  newChat: () => Promise<void>;
  openConversation: (id: string) => Promise<void>;
  retry: () => Promise<void>;
};

const ChatContext = createContext<ChatController | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const stateRef = useRef(state);
  const busy = useRef(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    stateRef.current = state;
  });

  useEffect(() => {
    const controller = new AbortController();
    listConversations(fetch, controller.signal)
      .then(async (conversations) => {
        if (controller.signal.aborted) {
          return;
        }
        dispatch({ type: "list", conversations });
        const newest = conversations[0];
        const current = stateRef.current;
        if (
          newest === undefined ||
          current.activeConversationId !== null ||
          current.messages.length > 0 ||
          current.status !== "idle"
        ) {
          return;
        }
        const detail = await loadConversation(newest.id, fetch, controller.signal);
        if (!controller.signal.aborted && stateRef.current.status === "idle") {
          dispatch({ type: "show", detail });
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        dispatch({ type: "notice", notice: messageFor(error) });
      });
    return () => controller.abort();
  }, []);

  const send = useCallback(async (text: string) => {
    const trimmed = text;
    if (trimmed.length < 1 || trimmed.length > 32_000) {
      return;
    }
    if (busy.current || !canSubmit(stateRef.current)) {
      return;
    }
    busy.current = true;
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      let summary = stateRef.current.conversations.find(
        (item) => item.id === stateRef.current.activeConversationId,
      );
      if (summary === undefined || stateRef.current.activeConversationId === null) {
        summary = await createConversation(fetch, controller.signal);
      }
      dispatch({
        type: "start-turn",
        conversation: summary,
        userId: crypto.randomUUID(),
        assistantId: crypto.randomUUID(),
        text: trimmed,
      });
      await streamChat({
        message: trimmed,
        conversationId: summary.id,
        signal: controller.signal,
        onEvent(event) {
          dispatch({ type: "event", event });
        },
      });
      dispatch({ type: "stream-end" });
    } catch (error) {
      if (isAbortError(error) || controller.signal.aborted) {
        dispatch({ type: "cancel" });
      } else {
        dispatch({ type: "fail", message: messageFor(error) });
      }
    } finally {
      busy.current = false;
      abortRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "cancel" });
  }, []);

  const newChat = useCallback(async () => {
    if (busy.current || !canSubmit(stateRef.current)) {
      return;
    }
    try {
      const summary = await createConversation();
      dispatch({
        type: "show",
        detail: { ...summary, messages: [] },
      });
    } catch (error) {
      dispatch({ type: "notice", notice: messageFor(error) });
    }
  }, []);

  const openConversation = useCallback(async (id: string) => {
    if (!canSubmit(stateRef.current)) {
      return;
    }
    try {
      const detail = await loadConversation(id);
      dispatch({ type: "show", detail });
    } catch (error) {
      dispatch({ type: "notice", notice: messageFor(error) });
    }
  }, []);

  const retry = useCallback(async () => {
    const text = lastUserText(stateRef.current);
    if (text === null || !canSubmit(stateRef.current)) {
      return;
    }
    await send(text);
  }, [send]);

  const controller = useMemo<ChatController>(
    () => ({ state, send, stop, newChat, openConversation, retry }),
    [state, send, stop, newChat, openConversation, retry],
  );

  return <ChatContext.Provider value={controller}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatController {
  const controller = useContext(ChatContext);
  if (controller === null) {
    throw new Error("Chat controls are unavailable.");
  }
  return controller;
}

function messageFor(error: unknown): string {
  if (error instanceof ChatHttpError) {
    return displayError({ status: error.status });
  }
  return displayError({});
}
