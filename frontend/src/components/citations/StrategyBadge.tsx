"use client";

import { Sparkles, Layers, Zap } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { RetrievalStrategy } from "@/lib/types";

const STRATEGY_CONFIG = {
  vectorless: {
    label: "Vectorless",
    icon: Sparkles,
    cls: "bg-[#7C3AED]/10 text-[#7C3AED] dark:bg-[#7C3AED]/20 dark:text-purple-300",
    description:
      "Structural tree navigation — no embeddings required. The LLM traverses the document hierarchy to locate the relevant section.",
  },
  hybrid: {
    label: "Hybrid",
    icon: Layers,
    cls: "bg-[#2E75B6]/10 text-[#2E75B6] dark:bg-[#2E75B6]/20 dark:text-blue-300",
    description:
      "Hybrid retrieval: dense Qdrant embeddings + BM25 sparse index. Used for cross-document queries.",
  },
  direct: {
    label: "Direct",
    icon: Zap,
    cls: "bg-neutral-500/10 text-neutral-500 dark:bg-neutral-700/30 dark:text-neutral-400",
    description:
      "Answered directly from model knowledge — no retrieval needed (factual, clarification, or math query).",
  },
} as const;

const UNKNOWN_STRATEGY_CONFIG = {
  label: "Unknown",
  icon: Zap,
  cls: "bg-muted text-muted-foreground",
  description: "Strategy not recorded for this answer.",
} as const;

interface StrategyBadgeProps {
  strategy: RetrievalStrategy | null;
  reasoning?: string | null;
  size?: "sm" | "default";
  className?: string;
}

export function StrategyBadge({
  strategy,
  reasoning,
  size = "default",
  className,
}: StrategyBadgeProps) {
  const cfg = (strategy && STRATEGY_CONFIG[strategy]) || UNKNOWN_STRATEGY_CONFIG;
  const Icon = cfg.icon;

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            role="status"
            aria-label={`Retrieval strategy: ${cfg.label}`}
            className={cn(
              "inline-flex items-center gap-1 rounded-full font-medium cursor-default select-none transition-colors",
              cfg.cls,
              size === "sm"
                ? "px-1.5 py-0.5 text-[10px]"
                : "px-2 py-0.5 text-xs",
              className
            )}
          >
            <Icon className={size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3"} />
            {cfg.label}
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[260px] text-xs space-y-1">
          <p className="font-medium text-foreground">{cfg.description}</p>
          {reasoning && (
            <p className="text-muted-foreground italic leading-snug">
              {reasoning}
            </p>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
