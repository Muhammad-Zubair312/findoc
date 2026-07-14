"use client";

import { ThumbsUp, ThumbsDown, Copy, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { formatLatency, formatCost } from "@/lib/utils";
import type { Message } from "@/lib/types";

interface FeedbackBarProps {
  message: Message;
  onFeedback: (feedback: "up" | "down") => void;
  onRegenerate: () => void;
  isStreaming?: boolean;
}

export function FeedbackBar({
  message,
  onFeedback,
  onRegenerate,
  isStreaming,
}: FeedbackBarProps) {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      toast.success("Answer copied", { duration: 2000 });
    } catch {
      toast.error("Could not access clipboard");
    }
  };

  const btnCls =
    "flex items-center justify-center rounded-md p-1.5 text-muted-foreground transition-colors duration-150 hover:text-foreground hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40";

  return (
    <div className="flex items-center gap-1 mt-3">
      {/* Thumbs up */}
      <button
        type="button"
        onClick={() => onFeedback("up")}
        disabled={isStreaming}
        aria-label="Good response"
        aria-pressed={message.feedback === "up"}
        className={cn(btnCls, message.feedback === "up" && "text-success bg-success/10")}
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </button>

      {/* Thumbs down */}
      <button
        type="button"
        onClick={() => onFeedback("down")}
        disabled={isStreaming}
        aria-label="Bad response"
        aria-pressed={message.feedback === "down"}
        className={cn(btnCls, message.feedback === "down" && "text-danger bg-danger/10")}
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </button>

      {/* Copy */}
      <button
        type="button"
        onClick={handleCopy}
        disabled={isStreaming || !message.content}
        aria-label="Copy answer"
        className={btnCls}
      >
        <Copy className="h-3.5 w-3.5" />
      </button>

      {/* Regenerate */}
      <button
        type="button"
        onClick={onRegenerate}
        disabled={isStreaming}
        aria-label="Regenerate response"
        className={btnCls}
      >
        <RotateCcw className="h-3.5 w-3.5" />
      </button>

      {/* Latency + cost — right-aligned, muted */}
      <div className="ml-auto flex items-center gap-2">
        {message.latency_ms !== null && message.latency_ms !== undefined && (
          <span className="text-[11px] font-mono text-muted-foreground/60">
            {formatLatency(message.latency_ms)}
          </span>
        )}
        {message.cost_usd !== null && message.cost_usd !== undefined && (
          <span className="text-[11px] font-mono text-muted-foreground/60">
            {formatCost(message.cost_usd)}
          </span>
        )}
      </div>
    </div>
  );
}
