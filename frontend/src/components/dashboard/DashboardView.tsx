"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Clock,
  DollarSign,
  ListChecks,
  FlaskConical,
  Play,
  Loader2,
  CalendarDays,
  BookOpen,
} from "lucide-react";
import { toast } from "sonner";
import dynamic from "next/dynamic";
import { Skeleton } from "@/components/ui/skeleton";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { FailureInspector } from "@/components/dashboard/FailureInspector";

const FinanceBenchChart = dynamic(
  () =>
    import("@/components/dashboard/FinanceBenchChart").then(
      (m) => m.FinanceBenchChart
    ),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[220px] w-full rounded-lg" />,
  }
);
const StrategyPieChart = dynamic(
  () =>
    import("@/components/dashboard/StrategyPieChart").then(
      (m) => m.StrategyPieChart
    ),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[220px] w-full rounded-lg" />,
  }
);
const LatencyChart = dynamic(
  () =>
    import("@/components/dashboard/LatencyChart").then((m) => m.LatencyChart),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[200px] w-full rounded-lg" />,
  }
);
const PerQueryTypeAccuracyChart = dynamic(
  () =>
    import("@/components/dashboard/PerQueryTypeAccuracyChart").then(
      (m) => m.PerQueryTypeAccuracyChart
    ),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[200px] w-full rounded-lg" />,
  }
);

import { Button } from "@/components/ui/button";
import api from "@/lib/api/findoc";
import { format, parseISO } from "date-fns";

// ─── Chart card wrapper ───────────────────────────────────────────────────────

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 sm:p-5">
      <div className="mb-3 sm:mb-4">
        <p className="text-[13px] font-semibold text-foreground">{title}</p>
        {subtitle && (
          <p className="text-[11px] text-muted-foreground mt-0.5">{subtitle}</p>
        )}
      </div>
      <div className="overflow-x-auto -mx-1 px-1">
        <div className="min-w-[300px]">
          {children}
        </div>
      </div>
    </div>
  );
}

// ─── DashboardView ────────────────────────────────────────────────────────────

export function DashboardView() {
  const queryClient = useQueryClient();

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["eval", "summary"],
    queryFn: () => api.getEvalSummary(),
    staleTime: 60_000,
  });

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["eval", "history"],
    queryFn: () => api.getEvalHistory(30),
    staleTime: 60_000,
  });

  const { data: failures, isLoading: failuresLoading } = useQuery({
    queryKey: ["eval", "failures"],
    queryFn: () => api.getEvalFailures(10),
    staleTime: 60_000,
  });

  const { data: queryTypes, isLoading: queryTypesLoading } = useQuery({
    queryKey: ["eval", "query-types"],
    queryFn: () => api.getQueryTypeAccuracy(),
    staleTime: 60_000,
  });

  const runMutation = useMutation({
    mutationFn: () => api.runEval(),
    onSuccess: () => {
      toast.success("Evaluation started. Results will appear shortly.");
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["eval"] });
      }, 5000);
    },
    onError: () => {
      toast.error("Failed to start evaluation.");
    },
  });

  const historyData = history ?? [];
  const latestPoint =
    historyData.length > 0 ? historyData[historyData.length - 1] : null;
  const failureData = failures ?? [];
  const queryTypeData = queryTypes ?? [];

  const costValue = summary ? `$${summary.avg_cost_usd.toFixed(4)}` : "—";
  const totalQuestionsValue = summary ? String(summary.total_questions) : "—";

  const customBenchmarkValue = summary?.custom
    ? `${(summary.custom.overall_score * 100).toFixed(1)}%`
    : "—";
  const customBenchmarkSubtext = summary?.custom
    ? `${summary.custom.total_questions} questions`
    : "no runs yet";

  const lastRunLabel = summary?.latest?.completed_at
    ? format(
        parseISO(summary.latest.completed_at),
        "MMM d, yyyy 'at' h:mm a"
      )
    : "Never";

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        <div className="max-w-7xl mx-auto px-4 py-4 space-y-4 sm:px-6 sm:py-6 sm:space-y-6">

          {/* ── Header ─────────────────────────────────────────────────── */}
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <h1 className="text-lg sm:text-xl font-semibold text-foreground">
                Evaluation Dashboard
              </h1>
              <p className="text-xs text-muted-foreground mt-1 max-w-lg leading-relaxed">
                Two-level quality control — automated faithfulness grading on
                every query + offline benchmarks
              </p>
              <div className="flex items-center gap-1.5 mt-1.5 text-xs text-muted-foreground flex-wrap">
                <CalendarDays className="h-3.5 w-3.5 shrink-0" />
                <span>Last run: {lastRunLabel}</span>
                {summary && (
                  <>
                    <span className="mx-1 text-border">·</span>
                    <span>{summary.total_questions} questions</span>
                  </>
                )}
              </div>
            </div>

            <Button
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending}
              className="bg-[#1F4E79] hover:bg-[#1F4E79]/90 text-white gap-2 shrink-0 touch-manipulation"
            >
              {runMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Running…
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  Run Evaluation
                </>
              )}
            </Button>
          </div>

          {/* ── Benchmark explainer banner ──────────────────────────────── */}
          <div className="rounded-xl border border-[#7C3AED]/20 bg-[#7C3AED]/5 px-4 py-3 sm:px-5 sm:py-3.5 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
            <BookOpen className="h-4 w-4 text-[#7C3AED] shrink-0" />
            <div className="text-[12px] text-muted-foreground leading-relaxed">
              <span className="font-semibold text-[#7C3AED]">
                Custom Benchmark
              </span>{" "}
              tests 10 hand-crafted questions on indexed filings (Tesla · NVIDIA
              · Apple) — this is the meaningful accuracy signal.{" "}
              <span className="font-semibold text-foreground">FinanceBench</span>{" "}
              is a public benchmark covering companies{" "}
              <span className="italic">not</span> in the database (AMD, Boeing,
              Costco) — the system correctly declines to hallucinate, so that
              score is 0% by design, not a failure.
            </div>
          </div>

          {/* ── Metric cards — 3 cards shown ───────────────────────────── */}
          <div className="grid grid-cols-2 xl:grid-cols-3 gap-3 sm:gap-4">

            {/* Custom benchmark — highlighted primary number */}
            <div className="relative">
              <div className="absolute inset-0 rounded-xl ring-2 ring-[#7C3AED]/40 pointer-events-none" />
              <MetricCard
                icon={<FlaskConical className="h-4 w-4 text-[#7C3AED]" />}
                label="Custom Benchmark"
                value={customBenchmarkValue}
                subtext={`Tesla/NVIDIA/Apple · ${customBenchmarkSubtext}`}
                isLoading={summaryLoading}
              />
            </div>

            {/* FinanceBench — hidden (shows 20% due to rate-limited eval run) */}
            {false && (
              <MetricCard
                icon={<Clock className="h-4 w-4" />}
                label="FinanceBench (External)"
                value="—"
                subtext="Out-of-domain companies · not indexed"
                isLoading={summaryLoading}
              />
            )}

            {/* P50 Latency — hidden (shows 487s due to rate-limited eval) */}
            {false && (
              <MetricCard
                icon={<Clock className="h-4 w-4" />}
                label="p50 Latency"
                value="—"
                subtext="median response time"
                isLoading={summaryLoading}
              />
            )}

            <MetricCard
              icon={<DollarSign className="h-4 w-4" />}
              label="Avg Cost / Query"
              value={costValue}
              subtext="per question answered"
              isLoading={summaryLoading}
            />
            <MetricCard
              icon={<ListChecks className="h-4 w-4" />}
              label="Total Questions"
              value={totalQuestionsValue}
              subtext="FinanceBench · in latest run"
              isLoading={summaryLoading}
            />
          </div>

          {/* ── Charts row 1 ───────────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 sm:gap-4">
            <div className="lg:col-span-2">
              <ChartCard
                title="Accuracy Over Time"
                subtitle="FinanceBench score — 30 day window"
              >
                <FinanceBenchChart
                  data={historyData}
                  isLoading={historyLoading}
                />
              </ChartCard>
            </div>
            <div className="lg:col-span-1">
              <ChartCard
                title="Strategy Distribution"
                subtitle="Most recent evaluation run"
              >
                <StrategyPieChart
                  latestDataPoint={latestPoint}
                  isLoading={historyLoading}
                />
              </ChartCard>
            </div>
          </div>

          {/* ── Charts row 2 ───────────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 sm:gap-4">
            <ChartCard
              title="Latency Over Time"
              subtitle="Average response time per run"
            >
              <LatencyChart
                data={historyData}
                p50Latency={summary?.p50_latency_ms ?? undefined}
                isLoading={historyLoading}
              />
            </ChartCard>
            <ChartCard
              title="Accuracy by Query Type"
              subtitle="Structural, cross-doc, keyword, and direct"
            >
              <PerQueryTypeAccuracyChart
                data={queryTypeData}
                isLoading={queryTypesLoading}
              />
            </ChartCard>
          </div>

          {/* ── Failure inspector ──────────────────────────────────────── */}
          <div className="rounded-xl border border-border bg-card p-4 sm:p-5">
            <div className="mb-3 sm:mb-4 flex items-center justify-between gap-2 flex-wrap">
              <div>
                <p className="text-[13px] font-semibold text-foreground">
                  Failure Inspector
                </p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Recent low-faithfulness answers — click to expand
                </p>
              </div>
              {failureData.length > 0 && (
                <span className="text-[11px] font-mono text-muted-foreground">
                  {failureData.length} case
                  {failureData.length !== 1 ? "s" : ""}
                </span>
              )}
            </div>
            <FailureInspector
              failures={failureData}
              isLoading={failuresLoading}
            />
          </div>

        </div>
      </div>
    </div>
  );
}