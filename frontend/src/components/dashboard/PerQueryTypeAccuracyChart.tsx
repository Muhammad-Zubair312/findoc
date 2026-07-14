"use client";

import { useState, useEffect } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import type { QueryTypeAccuracy } from "@/lib/types";

const QUERY_TYPE_LABELS: Record<string, string> = {
  structural: "Structural",
  cross_doc: "Cross-Doc",
  keyword: "Keyword",
  direct: "Direct",
};

function accuracyColor(accuracy: number): string {
  if (accuracy >= 0.9) return "#10B981"; // success
  if (accuracy >= 0.75) return "#2E75B6"; // accent-blue
  if (accuracy >= 0.6) return "#F59E0B"; // warning
  return "#EF4444"; // danger
}

interface PerQueryTypeAccuracyChartProps {
  data: QueryTypeAccuracy[];
  isLoading: boolean;
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { value: number; payload: QueryTypeAccuracy }[];
}) {
  if (!active || !payload?.length) return null;
  const { payload: entry } = payload[0];
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 shadow-lg text-[12px]">
      <p className="font-medium text-foreground mb-1">
        {QUERY_TYPE_LABELS[entry.query_type] ?? entry.query_type}
      </p>
      <p className="text-muted-foreground">
        Accuracy:{" "}
        <span
          className="font-mono font-semibold"
          style={{ color: accuracyColor(entry.accuracy) }}
        >
          {(entry.accuracy * 100).toFixed(1)}%
        </span>
      </p>
      <p className="text-muted-foreground">
        Questions: <span className="font-mono">{entry.count}</span>
      </p>
    </div>
  );
}

export function PerQueryTypeAccuracyChart({
  data,
  isLoading,
}: PerQueryTypeAccuracyChartProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  if (isLoading || !mounted) {
    return <Skeleton className="h-[200px] w-full rounded-lg" />;
  }

  if (data.length === 0) {
    return (
      <div className="h-[200px] flex items-center justify-center">
        <p className="text-sm text-muted-foreground">No query type data yet.</p>
      </div>
    );
  }

  const chartData = data.map((d) => ({
    ...d,
    label: QUERY_TYPE_LABELS[d.query_type] ?? d.query_type,
  }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart
        data={chartData}
        margin={{ top: 4, right: 8, left: -8, bottom: 0 }}
        barSize={24}
      >
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="hsl(var(--border))"
          vertical={false}
        />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          domain={[0, 1]}
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
          width={40}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(var(--muted)/0.4)" }} />
        <Bar dataKey="accuracy" radius={[3, 3, 0, 0]}>
          {chartData.map((entry) => (
            <Cell
              key={entry.query_type}
              fill={accuracyColor(entry.accuracy)}
              fillOpacity={0.85}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
