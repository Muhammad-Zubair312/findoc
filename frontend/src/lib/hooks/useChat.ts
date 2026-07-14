"use client";

import { useCallback, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { useChatStore } from "@/lib/stores/chatStore";
import api from "@/lib/api/findoc";
import type { WSEvent, Message } from "@/lib/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
const WS_CONNECT_TIMEOUT_MS = 12_000;

export function useChat(conversationId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const sendingRef = useRef(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);

  const {
    conversations,
    isStreaming,
    streaming,
    setActiveConversation,
    setMessages,
    addMessage,
    startStreaming,
    appendToken,
    setCitations,
    setRetrying,
    stopStreaming,
    clearStreaming,
    updateMessageId,  // ← NEW
  } = useChatStore();

  const messages = conversationId
    ? (conversations[conversationId] ?? [])
    : [];

  // ─── History fetch ────────────────────────────────────────────────────────
  const { isLoading: isLoadingHistory } = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: async () => {
      if (!conversationId) return [];
      const msgs = await api.getMessages(conversationId);
      const local =
        useChatStore.getState().conversations[conversationId] ?? [];
      if (msgs.length >= local.length) {
        setMessages(conversationId, msgs);
      }
      return msgs;
    },
    enabled: !!conversationId,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  // ─── Cleanup helper ───────────────────────────────────────────────────────
  const resetSendState = useCallback(() => {
    sendingRef.current = false;
    setIsConnecting(false);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  // ─── send ─────────────────────────────────────────────────────────────────
  const send = useCallback(
    async (query: string, documentIds: string[]) => {
      if (!conversationId || isStreaming || sendingRef.current) return;
      sendingRef.current = true;

      const userMessage: Message = {
        id: crypto.randomUUID(),
        conversation_id: conversationId,
        role: "user",
        content: query,
        citations: [],
        strategy_used: null,
        strategy_predicted: null,
        reasoning_trace: null,
        faithfulness_score: null,
        latency_ms: null,
        cost_usd: null,
        feedback: null,
        created_at: new Date().toISOString(),
      };
      addMessage(conversationId, userMessage);

      const assistantId = crypto.randomUUID();
      const placeholderAssistant: Message = {
        id: assistantId,
        conversation_id: conversationId,
        role: "assistant",
        content: "",
        citations: [],
        strategy_used: null,
        strategy_predicted: null,
        reasoning_trace: null,
        faithfulness_score: null,
        latency_ms: null,
        cost_usd: null,
        feedback: null,
        created_at: new Date().toISOString(),
      };
      addMessage(conversationId, placeholderAssistant);

      setIsConnecting(true);

      timeoutRef.current = setTimeout(() => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) {
          wsRef.current?.close();
          toast.error("Connection timed out — please try again.", {
            duration: 8000,
          });
          clearStreaming();
          resetSendState();
        }
      }, WS_CONNECT_TIMEOUT_MS);

      const ws = new WebSocket(`${WS_URL}/chat/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
          timeoutRef.current = null;
        }

        try {
          ws.send(
            JSON.stringify({
              conversation_id: conversationId,
              message: query,
              document_ids: documentIds,
              session_id: assistantId,
            })
          );
        } catch (err) {
          toast.error("Failed to send message — please try again.", {
            duration: 8000,
          });
          clearStreaming();
          resetSendState();
          ws.close();
          return;
        }

        setIsConnecting(false);
      };

      ws.onmessage = (event: MessageEvent) => {
        const data = JSON.parse(event.data as string) as WSEvent;

        switch (data.type) {
          case "start":
            startStreaming(assistantId, data.strategy_predicted);
            break;
          case "token":
            appendToken(data.content);
            break;
          case "citations":
            setCitations(data.citations);
            break;
          case "grader":
            if (data.retry) {
              setRetrying("Regenerating with better retrieval...");
            }
            break;
          case "end":
            // ── Replace local UUID with real DB UUID before stopStreaming ──
            // Backend now sends message_id in the "end" event (saved to DB
            // before sending end, so the UUID is guaranteed to exist).
            // This makes feedback (thumbs up/down) work — previously the
            // frontend sent crypto.randomUUID() which was never in the DB.
            if (data.message_id && conversationId) {
              updateMessageId(conversationId, assistantId, data.message_id);
            }
            stopStreaming({
              latency_ms: data.latency_ms,
              cost_usd: data.cost_usd,
              strategy_used: data.strategy_used,
              reasoning_trace: data.reasoning_trace,
            });
            sendingRef.current = false;
            ws.close();
            break;
          case "error":
            toast.error(data.message, { duration: 8000 });
            clearStreaming();
            resetSendState();
            ws.close();
            break;
        }
      };

      ws.onerror = () => {
        toast.error("Connection error — please try again.", {
          duration: 8000,
          action: {
            label: "Reconnect",
            onClick: () => send(query, documentIds),
          },
        });
        clearStreaming();
        resetSendState();
      };

      ws.onclose = (e) => {
        setIsConnecting(false);
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
          timeoutRef.current = null;
        }
        if (e.code !== 1000) {
          if (isStreaming) clearStreaming();
          sendingRef.current = false;
        }
      };
    },
    [
      conversationId,
      isStreaming,
      addMessage,
      startStreaming,
      appendToken,
      setCitations,
      setRetrying,
      stopStreaming,
      clearStreaming,
      resetSendState,
      updateMessageId,  // ← NEW
    ]
  );

  // ─── stop ─────────────────────────────────────────────────────────────────
  const stop = useCallback(() => {
    wsRef.current?.close(1000);
    clearStreaming();
    resetSendState();
  }, [clearStreaming, resetSendState]);

  // ─── regenerate ───────────────────────────────────────────────────────────
  const regenerate = useCallback(
    async (messageId: string) => {
      if (!conversationId) return;
      const msgs = conversations[conversationId] ?? [];
      const idx = msgs.findIndex((m) => m.id === messageId);
      if (idx <= 0) return;
      const prevUser = msgs[idx - 1];
      if (prevUser.role !== "user") return;
      await send(
        prevUser.content,
        useChatStore.getState().selectedDocumentIds
      );
    },
    [conversationId, conversations, send]
  );

  return {
    messages,
    isLoading: isLoadingHistory,
    isStreaming,
    isConnecting,
    streaming,
    send,
    stop,
    regenerate,
    setActiveConversation,
  };
}