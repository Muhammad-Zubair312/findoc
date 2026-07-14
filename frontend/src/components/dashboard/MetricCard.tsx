"use client";

import type { ReactNode } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  icon: ReactNode;
  label: string;
  value: string;
  subtext?: string;
  delta?: number;
  deltaLabel?: string;
  deltaPositiveIsBad?: boolean;
  isLoading?: boolean;
}

export function MetricCard({
  icon,
  label,
  value,
  subtext,
  delta,
  deltaLabel,
  deltaPositiveIsBad = false,
  isLoading = false,
}: MetricCardProps) {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-border bg-card p-5 space-y-3">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-10 w-20" />
        <Skeleton className="h-3 w-16" />
      </div>
    );
  }

  const hasDelta = delta !== undefined && delta !== 0;
  const isPositive = delta !== undefined && delta > 0;
  const isGood = deltaPositiveIsBad ? !isPositive : isPositive;

  return (
    <div className="rounded-xl border border-border bg-card p-5 flex flex-col gap-2 hover:shadow-sm transition-shadow duration-150">
      {/* Header: icon + label */}
      <div className="flex items-center gap-2 text-muted-foreground">
        <span className="shrink-0">{icon}</span>
        <span className="text-[12px] font-medium uppercase tracking-wide truncate">
          {label}
        </span>
      </div>

      {/* Value */}
      <div className="flex items-end gap-3">
        <span className="text-3xl font-bold text-foreground leading-none tabular-nums">
          {value}
        </span>

        {hasDelta && (
          <span
            className={cn(
              "flex items-center gap-0.5 text-[12px] font-medium mb-0.5",
              isGood ? "text-success" : "text-danger"
            )}
          >
            {isPositive ? (
              <TrendingUp className="h-3.5 w-3.5" />
            ) : (
              <TrendingDown className="h-3.5 w-3.5" />
            )}
            {isPositive ? "+" : ""}
            {deltaLabel ?? delta.toFixed(1)}
          </span>
        )}

        {delta === 0 && (
          <span className="flex items-center gap-0.5 text-[12px] font-medium text-muted-foreground mb-0.5">
            <Minus className="h-3.5 w-3.5" />
            No change
          </span>
        )}
      </div>

      {/* Subtext */}
      {subtext && (
        <p className="text-[11px] text-muted-foreground">{subtext}</p>
      )}
    </div>
  );
}
