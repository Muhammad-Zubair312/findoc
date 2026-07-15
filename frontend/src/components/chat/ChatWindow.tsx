"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { PanelRightClose, PanelRightOpen, X } from "lucide-react";
import { toast } from "sonner";

import { MessageList } from "@/components/chat/MessageList";
import { ChatInput } from "@/components/chat/ChatInput";
import { SourceTreePanel } from "@/components/citations/SourceTreePanel";
import { useChat } from "@/lib/hooks/useChat";
import { useChatStore } from "@/lib/stores/chatStore";
import { useUIStore } from "@/lib/stores/uiStore";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip";
import api from "@/lib/api/findoc";
import { cn } from "@/lib/utils";

interface ChatWindowProps {
  conversationId: string | null;
}

export function ChatWindow({ conversationId }: ChatWindowProps) {
  const router = useRouter();
  const [pendingInputValue, setPendingInputValue] = useState<
    string | undefined
  >(undefined);
  const [isCreatingConversation, setIsCreatingConversation] = useState(false);
  const consumedPendingMessageRef = useRef<string | null>(null);

  const {
    messages,
    isStreaming,
    isConnecting,
    send,
    regenerate,
    setActiveConversation,
  } = useChat(conversationId);

  const {
    selectedDocumentIds,
    pendingFirstMessage,
    setPendingFirstMessage,
    setSelectedDocuments,
  } = useChatStore();

  const { sourcePanelOpen, toggleSourcePanel, setSourcePanelOpen } =
    useUIStore();

  useEffect(() => {
    setActiveConversation(conversationId);
    return () => setActiveConversation(null);
  }, [conversationId, setActiveConversation]);

  useEffect(() => {
    if (
      pendingFirstMessage &&
      conversationId &&
      consumedPendingMessageRef.current !== pendingFirstMessage
    ) {
      consumedPendingMessageRef.current = pendingFirstMessage;
      const msg = pendingFirstMessage;
      setPendingFirstMessage(null);
      send(msg, selectedDocumentIds);
    }
  }, [
    conversationId,
    pendingFirstMessage,
    setPendingFirstMessage,
    send,
    selectedDocumentIds,
  ]);

  useEffect(() => {
    if (selectedDocumentIds.length > 0) {
      setSourcePanelOpen(true);
    }
  }, [selectedDocumentIds, setSourcePanelOpen]);

  // ── FIX: panel can open when docs selected OR when any message has citations
  const hasCitations = messages.some(
    (m) => m.citations && m.citations.length > 0
  );
  const canShowPanel = selectedDocumentIds.length > 0 || hasCitations;
  const showSourcePanel = sourcePanelOpen && canShowPanel;

  const handleSend = useCallback(
    async (query: string, docIds: string[]) => {
      if (!conversationId) {
        setIsCreatingConversation(true);
        try {
          const convo = await api.createConversation(docIds);
          setSelectedDocuments(docIds);
          setPendingFirstMessage(query);
          router.push(`/chat/${convo.id}`);
        } catch {
          toast.error("Failed to start conversation. Please try again.");
          setIsCreatingConversation(false);
        }
        return;
      }
      send(query, docIds);
    },
    [
      conversationId,
      send,
      router,
      setSelectedDocuments,
      setPendingFirstMessage,
    ]
  );

  const handleSuggestSelect = useCallback(
    (query: string) => {
      handleSend(query, selectedDocumentIds);
    },
    [handleSend, selectedDocumentIds]
  );

  const handleRegenerate = useCallback(
    (messageId: string) => {
      regenerate(messageId);
    },
    [regenerate]
  );

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Center column: chat ───────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">

        {/* Source panel toggle — shown when docs selected OR citations exist */}
        {canShowPanel && (
          <div className="flex items-center justify-end px-3 pt-2 pb-0 sm:px-4">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleSourcePanel}
                    className="h-7 w-7 text-muted-foreground hover:text-foreground"
                    aria-label={
                      sourcePanelOpen
                        ? "Hide source panel"
                        : "Show source panel"
                    }
                  >
                    {sourcePanelOpen ? (
                      <PanelRightClose className="h-4 w-4" />
                    ) : (
                      <PanelRightOpen className="h-4 w-4" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="left">
                  {sourcePanelOpen ? "Hide source panel" : "Show source panel"}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        )}

        {/* Message list */}
        <MessageList
          messages={messages}
          conversationId={conversationId}
          onSuggestSelect={handleSuggestSelect}
          onRegenerate={handleRegenerate}
        />

        {/* Chat input */}
        <ChatInput
          onSend={handleSend}
          disabled={isStreaming || isCreatingConversation || isConnecting}
          placeholder={isConnecting ? "Connecting..." : undefined}
          initialValue={pendingInputValue}
          onInitialValueConsumed={() => setPendingInputValue(undefined)}
        />
      </div>

      {/* ── Source panel: DESKTOP (lg+) sidebar ──────────────────────────── */}
      <AnimatePresence>
        {showSourcePanel && (
          <motion.aside
            key="source-panel-desktop"
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 380, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="hidden lg:block shrink-0 overflow-hidden border-l border-border bg-card"
            aria-label="Source panel"
          >
            <div className="h-full w-[380px]">
              <SourceTreePanel selectedDocumentIds={selectedDocumentIds} />
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* ── Source panel: MOBILE (< lg) full-screen drawer ───────────────── */}
      <AnimatePresence>
        {showSourcePanel && (
          <>
            <motion.div
              key="source-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-30 bg-background/70 backdrop-blur-sm lg:hidden"
              onClick={toggleSourcePanel}
              aria-hidden="true"
            />
            <motion.aside
              key="source-panel-mobile"
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className={cn(
                "fixed right-0 top-0 bottom-0 z-40 lg:hidden",
                "w-full sm:w-[380px]",
                "overflow-hidden border-l border-border bg-card shadow-2xl"
              )}
              aria-label="Source panel"
            >
              <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                <span className="text-sm font-semibold text-foreground">
                  Sources
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={toggleSourcePanel}
                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  aria-label="Close source panel"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="h-[calc(100%-52px)] overflow-y-auto">
                <SourceTreePanel selectedDocumentIds={selectedDocumentIds} />
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}