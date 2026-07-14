"use client";

import { useState, useEffect } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import type { EvalDataPoint } from "@/lib/types";
import { format, parseISO } from "date-fns";

interface FinanceBenchChartProps {
  data: EvalDataPoint[];
  isLoading: boolean;
}

interface TooltipPayload {
  value: number;
  dataKey: string;
  color: string;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
}) {
  if (!active || !payload?.length || !label) return null;

  const accuracy = payload.find((p) => p.dataKey === "accuracy");

  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 shadow-lg text-[12px]">
      <p className="font-medium text-foreground mb-1.5">
        {format(parseISO(label), "MMM d, yyyy")}
      </p>
      {accuracy && (
        <p className="text-[#7C3AED]">
          Accuracy: <span className="font-mono font-semibold">{(accuracy.value * 100).toFixed(1)}%</span>
        </p>
      )}
    </div>
  );
}

export function FinanceBenchChart({ data, isLoading }: FinanceBenchChartProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  if (isLoading || !mounted) {
    return <Skeleton className="h-[220px] w-full rounded-lg" />;
  }

  if (data.length === 0) {
    return (
      <div className="h-[220px] flex items-center justify-center">
        <p className="text-sm text-muted-foreground">No evaluation history yet.</p>
      </div>
    );
  }

  const chartData = data.map((d) => ({
    ...d,
    accuracy: Math.round(d.accuracy * 1000) / 1000,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="accuracyGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#7C3AED" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#7C3AED" stopOpacity={0} />
          </linearGradient>
        </defs>
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
          tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          domain={[0.5, 1.0]}
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="accuracy"
          stroke="#7C3AED"
          strokeWidth={2}
          fill="url(#accuracyGrad)"
          dot={false}
          activeDot={{ r: 4, fill: "#7C3AED", strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
