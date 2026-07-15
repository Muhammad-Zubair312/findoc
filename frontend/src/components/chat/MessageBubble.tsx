"use client";

import React, { memo, useMemo } from "react";
import Image from "next/image";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type { Components } from "react-markdown";
import { motion, AnimatePresence } from "framer-motion";

import { StrategyBadge } from "@/components/citations/StrategyBadge";
import { StreamingCursor } from "@/components/chat/StreamingCursor";
import { FeedbackBar } from "@/components/chat/FeedbackBar";
import { CodeBlock } from "@/components/chat/CodeBlock";
import { useFeedback } from "@/lib/hooks/useFeedback";
import { useUIStore } from "@/lib/stores/uiStore";
import type { Message, Citation, RetrievalStrategy } from "@/lib/types";
import { cn } from "@/lib/utils";

// ─── Markdown component overrides ────────────────────────────────────────────

const markdownComponents: Components = {
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,

  code: ({ className, children, ...props }) => {
    const isBlock = !!className;
    if (isBlock) {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code
        className="font-mono text-[13px] bg-muted rounded px-1.5 py-0.5 text-foreground"
        {...props}
      >
        {children}
      </code>
    );
  },

  blockquote: ({ children, ...props }) => (
    <blockquote
      className="border-l-[3px] border-[#7C3AED] pl-4 my-3 italic text-muted-foreground"
      {...props}
    >
      {children}
    </blockquote>
  ),

  a: ({ href, children, ...props }) => (
    <a
      href={href}
      className="text-[#2E75B6] underline-offset-2 hover:underline"
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    >
      {children}
    </a>
  ),

  // Tables scroll horizontally on mobile — already handled here
  table: ({ children, ...props }) => (
    <div className="my-4 overflow-x-auto rounded-lg border border-border scrollbar-thin">
      <table className="min-w-full text-sm" {...props}>
        {children}
      </table>
    </div>
  ),
  thead: ({ children, ...props }) => (
    <thead
      className="bg-muted/50 text-xs uppercase tracking-wider"
      {...props}
    >
      {children}
    </thead>
  ),
  tbody: ({ children, ...props }) => (
    <tbody className="divide-y divide-border" {...props}>
      {children}
    </tbody>
  ),
  tr: ({ children, ...props }) => (
    <tr className="even:bg-muted/30 transition-colors" {...props}>
      {children}
    </tr>
  ),
  th: ({ children, ...props }) => (
    <th
      className="px-3 py-2 text-left font-semibold text-muted-foreground"
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td className="px-3 py-2 text-foreground" {...props}>
      {children}
    </td>
  ),

  h1: ({ children, ...props }) => (
    <h1
      className="text-xl font-semibold mt-4 mb-2 text-foreground"
      {...props}
    >
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2
      className="text-lg font-semibold mt-4 mb-2 text-foreground"
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3
      className="text-base font-semibold mt-3 mb-1.5 text-foreground"
      {...props}
    >
      {children}
    </h3>
  ),

  ul: ({ children, ...props }) => (
    <ul
      className="my-2 ml-4 list-disc space-y-1 marker:text-muted-foreground"
      {...props}
    >
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="my-2 ml-4 list-decimal space-y-1" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="leading-relaxed" {...props}>
      {children}
    </li>
  ),

  p: ({ children, ...props }) => (
    <p className="leading-relaxed mb-2 last:mb-0" {...props}>
      {children}
    </p>
  ),
};

// ─── Premium Typing Indicator ─────────────────────────────────────────────────

const TypingIndicator = memo(function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.2 }}
      className="flex items-center gap-3 py-1"
    >
      <div className="flex items-center gap-[5px]">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="h-[8px] w-[8px] rounded-full bg-[#5B21B6]"
            animate={{
              y: [0, -6, 0],
              opacity: [0.7, 1, 0.7],
              scale: [0.9, 1.2, 0.9],
            }}
            transition={{
              duration: 0.7,
              repeat: Infinity,
              delay: i * 0.14,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>
      <motion.span
        className="text-[11px] font-medium text-[#5B21B6] tracking-wide"
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
      >
        Analyzing filing...
      </motion.span>
    </motion.div>
  );
});

// ─── Types ────────────────────────────────────────────────────────────────────

interface MessageBubbleProps {
  message: Message;
  isActiveStream?: boolean;
  streamingContent?: string;
  streamingCitations?: Citation[];
  streamingStrategy?: RetrievalStrategy | null;
  isRetrying?: boolean;
  retryMessage?: string | null;
  onRegenerate: () => void;
  isStreaming: boolean;
}

// ─── User bubble ──────────────────────────────────────────────────────────────

const UserBubble = memo(function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      {/*
       * max-w-[92%] on mobile prevents the bubble from touching screen edges.
       * sm:max-w-2xl gives the comfortable desktop width.
       */}
      <div className="max-w-[92%] sm:max-w-2xl rounded-2xl bg-secondary px-4 py-3 text-sm text-foreground leading-relaxed">
        {content}
      </div>
    </div>
  );
});

// ─── Assistant bubble ─────────────────────────────────────────────────────────

const AssistantBubble = memo(function AssistantBubble({
  message,
  isActiveStream,
  streamingContent,
  streamingCitations,
  streamingStrategy,
  isRetrying,
  retryMessage,
  onRegenerate,
  isStreaming,
}: MessageBubbleProps) {
  const feedback = useFeedback();
  const setActiveSourceTab = useUIStore((s) => s.setActiveSourceTab);
  const setSourcePanelOpen = useUIStore((s) => s.setSourcePanelOpen);
  
  const displayContent = isActiveStream
    ? (streamingContent ?? "")
    : message.content;
  const displayCitations = isActiveStream
    ? (streamingCitations ?? [])
    : message.citations;
  const displayStrategy = isActiveStream
    ? (streamingStrategy ?? message.strategy_predicted)
    : (message.strategy_used ?? message.strategy_predicted);

  const isEmpty = !displayContent && !isActiveStream;
  const isWaitingForFirstToken = isActiveStream && !displayContent;

  const handleFeedback = (fb: "up" | "down") => {
    feedback.mutate({ message_id: message.id, feedback: fb });
  };

  const handleCitationClick = (_idx: number) => {
    setSourcePanelOpen(true);        // opens the panel
    setActiveSourceTab("citations"); // switches to citations tab
};

  const renderedMarkdown = useMemo(
    () => (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={markdownComponents}
      >
        {displayContent}
      </ReactMarkdown>
    ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [displayContent]
  );

  return (
    // gap-2 on mobile, gap-3 on sm+ — avatar + content less cramped on small screens
    <div className="flex gap-2 sm:gap-3 group">
      {/* Avatar — glows while streaming */}
      <div className="shrink-0 mt-0.5 relative">
        {isActiveStream && (
          <motion.div
            className="absolute inset-0 rounded-full bg-[#7C3AED]/30"
            animate={{ scale: [1, 1.55, 1], opacity: [0.5, 0, 0.5] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
          />
        )}
        <div
          className={cn(
            "relative flex h-6 w-6 items-center justify-center rounded-full bg-[#1F4E79] transition-all duration-300",
            isActiveStream && "ring-1 ring-[#7C3AED]/40"
          )}
        >
          <Image src="/logo.svg" alt="FinDoc" width={14} height={14} />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-2">
        {/* Strategy badge + retry label */}
        {displayStrategy && (
          <div className="flex items-center gap-2 flex-wrap">
            <StrategyBadge
              strategy={displayStrategy}
              reasoning={message.reasoning_trace}
              size="sm"
            />
            {isRetrying && (
              <span className="text-[11px] text-warning animate-pulse-subtle">
                {retryMessage ?? "Regenerating with better retrieval..."}
              </span>
            )}
          </div>
        )}

        {/* Premium typing indicator */}
        <AnimatePresence mode="wait">
          {isWaitingForFirstToken && <TypingIndicator key="typing" />}
        </AnimatePresence>

        {/* Message body */}
        <AnimatePresence>
          {!isEmpty && (
            <motion.div
              key="content"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.15 }}
              className="prose-chat text-sm leading-relaxed text-foreground"
            >
              {renderedMarkdown}
              {isActiveStream && <StreamingCursor />}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Citation chips — larger touch targets on mobile */}
        {displayCitations.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {displayCitations.map((citation, idx) => (
              <button
                key={citation.id}
                type="button"
                onClick={() => handleCitationClick(idx)}
                className="inline-flex items-center rounded-full border border-[#2E75B6]/30 bg-[#2E75B6]/8
                           px-2.5 py-1 text-[11px] font-medium text-[#2E75B6]
                           hover:bg-[#2E75B6]/15 transition-colors touch-manipulation"
                aria-label={`Source ${idx + 1}`}
              >
                [{idx + 1}]
              </button>
            ))}
          </div>
        )}

        {/* Feedback bar */}
        {!isActiveStream && message.content && (
          <FeedbackBar
            message={message}
            onFeedback={handleFeedback}
            onRegenerate={onRegenerate}
            isStreaming={isStreaming}
          />
        )}
      </div>
    </div>
  );
});

// ─── Main export ──────────────────────────────────────────────────────────────

export const MessageBubble = memo(function MessageBubble(
  props: MessageBubbleProps
) {
  const { message } = props;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      {message.role === "user" ? (
        <UserBubble content={message.content} />
      ) : (
        <AssistantBubble {...props} />
      )}
    </motion.div>
  );
});