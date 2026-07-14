"use client";

import { ArrowRight } from "lucide-react";
import { StrategyBadge } from "@/components/citations/StrategyBadge";
import type { Citation } from "@/lib/types";
import { cn } from "@/lib/utils";

interface CitationCardProps {
  citation: Citation;
  index: number;
  isHighlighted: boolean;
  onHoverEnter: () => void;
  onHoverLeave: () => void;
  onReadMore: () => void;
}

export function CitationCard({
  citation,
  index,
  isHighlighted,
  onHoverEnter,
  onHoverLeave,
  onReadMore,
}: CitationCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border p-3 transition-all duration-150",
        "hover:bg-neutral-100 dark:hover:bg-neutral-800/60",
        isHighlighted &&
          "border-[#7C3AED]/40 bg-[#7C3AED]/5 dark:bg-[#7C3AED]/8"
      )}
      onMouseEnter={onHoverEnter}
      onMouseLeave={onHoverLeave}
    >
      {/* Top row: badge + title + page */}
      <div className="flex items-start gap-2 mb-2">
        <div className="shrink-0 mt-px">
          <StrategyBadge strategy={citation.strategy} size="sm" />
        </div>
        <span className="flex-1 min-w-0 text-[13px] font-medium text-foreground leading-snug">
          <span className="text-[11px] font-mono text-muted-foreground mr-1.5 shrink-0">
            [{index + 1}]
          </span>
          {citation.section_title}
        </span>
        <span className="shrink-0 text-[10px] font-mono text-muted-foreground bg-muted rounded px-1.5 py-0.5 whitespace-nowrap">
          p.{citation.page_start}
          {citation.page_end !== citation.page_start && `–${citation.page_end}`}
        </span>
      </div>

      {/* Excerpt */}
      <p className="text-[13px] text-muted-foreground leading-relaxed line-clamp-3 mb-2.5">
        {citation.excerpt}
      </p>

      {/* Read more */}
      <button
        type="button"
        onClick={onReadMore}
        className="flex items-center gap-1 text-xs text-[#2E75B6] hover:underline underline-offset-4 transition-colors"
      >
        Read full section
        <ArrowRight className="h-3 w-3" />
      </button>
    </div>
  );
}
