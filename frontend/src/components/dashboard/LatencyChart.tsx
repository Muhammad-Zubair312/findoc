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
  ReferenceLine,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import type { EvalDataPoint } from "@/lib/types";
import { format, parseISO } from "date-fns";

interface LatencyChartProps {
  data: EvalDataPoint[];
  p50Latency?: number;
  isLoading: boolean;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}) {
  if (!active || !payload?.length || !label) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 shadow-lg text-[12px]">
      <p className="font-medium text-foreground mb-1">
        {format(parseISO(label), "MMM d, yyyy")}
      </p>
      <p className="text-[#2E75B6]">
        Avg latency:{" "}
        <span className="font-mono font-semibold">{Math.round(payload[0].value)}ms</span>
      </p>
    </div>
  );
}

export function LatencyChart({ data, p50Latency, isLoading }: LatencyChartProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  if (isLoading || !mounted) {
    return <Skeleton className="h-[200px] w-full rounded-lg" />;
  }

  if (data.length === 0) {
    return (
      <div className="h-[200px] flex items-center justify-center">
        <p className="text-sm text-muted-foreground">No latency history yet.</p>
      </div>
    );
  }

  const maxLatency = Math.max(...data.map((d) => d.avg_latency_ms));
  const yMax = Math.ceil(maxLatency * 1.2 / 500) * 500;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -8, bottom: 0 }} barSize={16}>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="hsl(var(--border))"
          vertical={false}
        />
        <XAxis
          dataKey="run_date"
          tickFormatter={(v: string) => format(parseISO(v), "MMM d")}
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(v: number) => `${v}ms`}
          domain={[0, yMax]}
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
          width={52}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(var(--muted)/0.4)" }} />
        {p50Latency && (
          <ReferenceLine
            y={p50Latency}
            stroke="#F59E0B"
            strokeDasharray="4 4"
            strokeWidth={1.5}
            label={{
              value: `p50: ${Math.round(p50Latency)}ms`,
              position: "right",
              fontSize: 10,
              fill: "#F59E0B",
            }}
          />
        )}
        <Bar
          dataKey="avg_latency_ms"
          fill="#2E75B6"
          radius={[3, 3, 0, 0]}
          fillOpacity={0.85}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
