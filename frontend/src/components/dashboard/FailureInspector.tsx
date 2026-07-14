"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { StrategyBadge } from "@/components/citations/StrategyBadge";
import type { FailureCase } from "@/lib/types";
import { cn } from "@/lib/utils";
import { format, parseISO } from "date-fns";

interface FailureInspectorProps {
  failures: FailureCase[];
  isLoading: boolean;
}

export function FailureInspector({ failures, isLoading }: FailureInspectorProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (failures.length === 0) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm text-muted-foreground">No failures recorded yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {failures.map((f) => (
        <FailureRow key={f.id} failure={f} />
      ))}
    </div>
  );
}

function FailureRow({ failure }: { failure: FailureCase }) {
  const [expanded, setExpanded] = useState(false);

  const scoreColor =
    failure.faithfulness_score >= 0.7
      ? "text-warning"
      : "text-danger";

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      {/* Row header */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className={cn(
          "w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-muted/40 transition-colors",
          expanded && "bg-muted/40"
        )}
        aria-expanded={expanded}
      >
        <span className="shrink-0 mt-0.5 text-muted-foreground">
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </span>

        <div className="flex-1 min-w-0">
          <p className="text-[13px] text-foreground leading-snug line-clamp-2">
            {failure.question}
          </p>
          <div className="flex items-center gap-3 mt-1.5 flex-wrap">
            <StrategyBadge strategy={failure.strategy_used} size="sm" />
            <span className={cn("text-[11px] font-mono font-semibold", scoreColor)}>
              {(failure.faithfulness_score * 100).toFixed(0)}% faithful
            </span>
            <span className="text-[11px] text-muted-foreground">
              {format(parseISO(failure.run_date), "MMM d, yyyy")}
            </span>
          </div>
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-border px-4 py-4 space-y-4 bg-muted/20">
          <AnswerBlock label="Gold Answer" content={failure.gold_answer} variant="success" />
          <AnswerBlock
            label="Predicted Answer"
            content={failure.predicted_answer}
            variant="danger"
          />

          {failure.grader_explanation && (
            <div>
              <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                Grader Explanation
              </p>
              <p className="text-[12px] text-muted-foreground leading-relaxed">
                {failure.grader_explanation}
              </p>
            </div>
          )}

          {failure.reasoning_trace && (
            <details className="group">
              <summary className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide cursor-pointer hover:text-foreground transition-colors select-none">
                Reasoning trace
              </summary>
              <pre className="mt-2 text-[11px] text-muted-foreground leading-relaxed whitespace-pre-wrap font-mono bg-muted/60 rounded-lg p-3 overflow-x-auto">
                {failure.reasoning_trace}
              </pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

function AnswerBlock({
  label,
  content,
  variant,
}: {
  label: string;
  content: string;
  variant: "success" | "danger";
}) {
  return (
    <div>
      <p
        className={cn(
          "text-[11px] font-semibold uppercase tracking-wide mb-1.5",
          variant === "success" ? "text-success" : "text-danger"
        )}
      >
        {label}
      </p>
      <p className="text-[13px] text-foreground leading-relaxed">{content}</p>
    </div>
  );
}
