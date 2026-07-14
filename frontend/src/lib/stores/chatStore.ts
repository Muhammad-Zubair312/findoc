import { create } from "zustand";
import type { Message, Citation, RetrievalStrategy } from "@/lib/types";

interface StreamingState {
  messageId: string | null;
  content: string;
  strategyPredicted: RetrievalStrategy | null;
  citations: Citation[];
  isRetrying: boolean;
  retryMessage: string | null;
}

interface ChatState {
  conversations: Record<string, Message[]>;
  activeConversationId: string | null;
  selectedDocumentIds: string[];
  streaming: StreamingState;
  isStreaming: boolean;
  pendingFirstMessage: string | null;

  setActiveConversation: (id: string | null) => void;
  setMessages: (conversationId: string, messages: Message[]) => void;
  addMessage: (conversationId: string, message: Message) => void;
  updateMessage: (
    conversationId: string,
    messageId: string,
    patch: Partial<Message>
  ) => void;
  // ── Replaces the local crypto.randomUUID() with the real DB UUID ──────────
  // Called from useChat when the backend sends message_id in the "end" event.
  // Without this, feedback always 404s because the frontend sends a UUID that
  // was never persisted — the backend generates its own UUID on insert.
  updateMessageId: (
    conversationId: string,
    oldId: string,
    newId: string
  ) => void;
  setSelectedDocuments: (ids: string[]) => void;
  addSelectedDocument: (id: string) => void;
  removeSelectedDocument: (id: string) => void;
  setPendingFirstMessage: (msg: string | null) => void;

  startStreaming: (messageId: string, strategyPredicted: RetrievalStrategy) => void;
  appendToken: (token: string) => void;
  setCitations: (citations: Citation[]) => void;
  setRetrying: (message: string) => void;
  stopStreaming: (patch?: {
    latency_ms: number;
    cost_usd: number;
    strategy_used: RetrievalStrategy;
    reasoning_trace: string;
  }) => void;
  clearStreaming: () => void;
}

const initialStreaming: StreamingState = {
  messageId: null,
  content: "",
  strategyPredicted: null,
  citations: [],
  isRetrying: false,
  retryMessage: null,
};

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: {},
  activeConversationId: null,
  selectedDocumentIds: [],
  streaming: initialStreaming,
  isStreaming: false,
  pendingFirstMessage: null,

  setActiveConversation: (id) => set({ activeConversationId: id }),

  setMessages: (conversationId, messages) =>
    set((s) => ({
      conversations: { ...s.conversations, [conversationId]: messages },
    })),

  addMessage: (conversationId, message) =>
    set((s) => ({
      conversations: {
        ...s.conversations,
        [conversationId]: [
          ...(s.conversations[conversationId] ?? []),
          message,
        ],
      },
    })),

  updateMessage: (conversationId, messageId, patch) =>
    set((s) => ({
      conversations: {
        ...s.conversations,
        [conversationId]: (s.conversations[conversationId] ?? []).map((m) =>
          m.id === messageId ? { ...m, ...patch } : m
        ),
      },
    })),

  updateMessageId: (conversationId, oldId, newId) =>
    set((s) => ({
      conversations: {
        ...s.conversations,
        [conversationId]: (s.conversations[conversationId] ?? []).map((m) =>
          m.id === oldId ? { ...m, id: newId } : m
        ),
      },
      // Also update streaming.messageId if it still holds the old local UUID
      // so stopStreaming() patches the right message when called right after.
      streaming:
        s.streaming.messageId === oldId
          ? { ...s.streaming, messageId: newId }
          : s.streaming,
    })),

  setSelectedDocuments: (ids) => set({ selectedDocumentIds: ids }),
  addSelectedDocument: (id) =>
    set((s) => ({
      selectedDocumentIds: s.selectedDocumentIds.includes(id)
        ? s.selectedDocumentIds
        : [...s.selectedDocumentIds, id],
    })),
  removeSelectedDocument: (id) =>
    set((s) => ({
      selectedDocumentIds: s.selectedDocumentIds.filter((d) => d !== id),
    })),
  setPendingFirstMessage: (msg) => set({ pendingFirstMessage: msg }),

  startStreaming: (messageId, strategyPredicted) =>
    set({
      isStreaming: true,
      streaming: {
        ...initialStreaming,
        messageId,
        strategyPredicted,
      },
    }),

  appendToken: (token) =>
    set((s) => ({
      streaming: {
        ...s.streaming,
        content: s.streaming.content + token,
      },
    })),

  setCitations: (citations) =>
    set((s) => ({
      streaming: { ...s.streaming, citations },
    })),

  setRetrying: (message) =>
    set((s) => ({
      streaming: {
        ...s.streaming,
        isRetrying: true,
        retryMessage: message,
        content: "",
      },
    })),

  stopStreaming: (patch) => {
    const { streaming, activeConversationId } = get();
    if (!activeConversationId || !streaming.messageId) {
      set({ isStreaming: false });
      return;
    }
    const finalMessage: Partial<Message> = {
      content: streaming.content,
      citations: streaming.citations,
      ...(patch ?? {}),
      strategy_used: patch?.strategy_used ?? streaming.strategyPredicted,
      strategy_predicted: streaming.strategyPredicted,
    };
    set((s) => ({
      isStreaming: false,
      conversations: {
        ...s.conversations,
        [activeConversationId]: (
          s.conversations[activeConversationId] ?? []
        ).map((m) =>
          m.id === streaming.messageId ? { ...m, ...finalMessage } : m
        ),
      },
      streaming: initialStreaming,
    }));
  },

  clearStreaming: () =>
    set({ isStreaming: false, streaming: initialStreaming }),
}));