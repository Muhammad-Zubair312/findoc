"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowDown } from "lucide-react";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { SuggestedPrompts } from "@/components/chat/SuggestedPrompts";
import { useChatStore } from "@/lib/stores/chatStore";
import type { Message } from "@/lib/types";

interface MessageListProps {
  messages: Message[];
  conversationId: string | null;
  onSuggestSelect: (query: string) => void;
  onRegenerate: (messageId: string) => void;
}

export function MessageList({
  messages,
  conversationId,
  onSuggestSelect,
  onRegenerate,
}: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [atBottom, setAtBottom] = useState(true);

  const { isStreaming, streaming } = useChatStore();

  // Track scroll position
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = el;
      setAtBottom(scrollHeight - scrollTop - clientHeight < 120);
    };

    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, []);

  // Auto-scroll when new messages or streaming content arrives
  useEffect(() => {
    if (atBottom && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "instant" });
    }
  }, [messages.length, streaming.content, atBottom]);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    setAtBottom(true);
  }, []);

  const isEmpty = messages.length === 0 && !isStreaming;

  return (
    <div className="relative flex-1 overflow-hidden">
      {/* Scrollable area */}
      <div
        ref={scrollRef}
        className="h-full overflow-y-auto scrollbar-thin px-4 md:px-6"
      >
        <div className="mx-auto max-w-3xl py-6 space-y-6">
          {isEmpty ? (
            <SuggestedPrompts onSelect={onSuggestSelect} />
          ) : (
            <>
              {messages.map((message) => {
                const isActiveStream =
                  isStreaming && streaming.messageId === message.id;

                return (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    isActiveStream={isActiveStream}
                    streamingContent={
                      isActiveStream ? streaming.content : undefined
                    }
                    streamingCitations={
                      isActiveStream ? streaming.citations : undefined
                    }
                    streamingStrategy={
                      isActiveStream ? streaming.strategyPredicted : undefined
                    }
                    isRetrying={isActiveStream ? streaming.isRetrying : undefined}
                    retryMessage={
                      isActiveStream ? streaming.retryMessage : undefined
                    }
                    onRegenerate={() => onRegenerate(message.id)}
                    isStreaming={isStreaming}
                  />
                );
              })}
            </>
          )}
          {/* Scroll anchor */}
          <div ref={bottomRef} className="h-px" />
        </div>
      </div>

      {/* Scroll-to-bottom FAB */}
      <AnimatePresence>
        {!atBottom && !isEmpty && (
          <motion.button
            initial={{ opacity: 0, scale: 0.8, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.8, y: 8 }}
            transition={{ duration: 0.15 }}
            type="button"
            onClick={scrollToBottom}
            className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-md hover:text-foreground hover:shadow-lg transition-all duration-150"
            aria-label="Scroll to bottom"
          >
            <ArrowDown className="h-3.5 w-3.5" />
            Scroll to bottom
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}
