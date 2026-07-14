"use client";

import { TrendingUp, FileSearch, GitCompare, BookOpen } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

const PROMPTS = [
  {
    icon: TrendingUp,
    label: "Gross margin",
    query: "What was Tesla's 2023 automotive gross margin?",
  },
  {
    icon: FileSearch,
    label: "Risk factors",
    query: "Summarize NVIDIA's main risk factors in their most recent 10-K",
  },
  {
    icon: GitCompare,
    label: "Cross-doc compare",
    query: "Compare R&D spending: Microsoft vs Tesla",
  },
  {
    icon: BookOpen,
    label: "Policy changes",
    query: "What were NVIDIA's main risk factors in their 2024 10-K?",
  },
] as const;

interface SuggestedPromptsProps {
  onSelect: (query: string) => void;
}

export function SuggestedPrompts({ onSelect }: SuggestedPromptsProps) {
  return (
    // py-8 on mobile (short phones), relaxes to py-16 on sm+
    <div className="flex flex-col items-center justify-center h-full px-4 py-8 sm:px-6 sm:py-16">

      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        // mb-6 on mobile, mb-10 on sm+
        className="text-center space-y-2 mb-6 sm:mb-10"
      >
        {/* Slightly smaller heading on mobile */}
        <h2 className="text-xl sm:text-2xl font-semibold tracking-tight text-foreground">
          What would you like to know?
        </h2>
        <p className="text-sm text-muted-foreground max-w-sm leading-relaxed">
          Ask about any SEC filing. FinDoc navigates the document structure to
          find the exact section — no keyword guessing.
        </p>
      </motion.div>

      {/* Prompt grid
          - 1 column always on mobile (cards are wide enough to be readable)
          - 2 columns on sm+ (matches the original design)
          - max-w-2xl keeps it centered on wide screens
      */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 sm:gap-3 w-full max-w-2xl">
        {PROMPTS.map(({ icon: Icon, label, query }, i) => (
          <motion.button
            key={query}
            type="button"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: 0.05 * i }}
            onClick={() => onSelect(query)}
            className={cn(
              "group flex items-start gap-3 rounded-xl border border-border bg-card text-left",
              // p-3 on mobile for compact feel, p-4 on sm+
              "p-3 sm:p-4",
              "hover:border-[#7C3AED]/40 hover:bg-[#7C3AED]/5 hover:shadow-sm",
              "transition-all duration-150",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              // Touch feedback
              "active:scale-[0.98] touch-manipulation"
            )}
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#7C3AED]/10 text-[#7C3AED] group-hover:bg-[#7C3AED]/20 transition-colors">
              <Icon className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground mb-0.5">
                {label}
              </p>
              <p className="text-sm text-foreground leading-snug line-clamp-2">
                {query}
              </p>
            </div>
          </motion.button>
        ))}
      </div>
    </div>
  );
}