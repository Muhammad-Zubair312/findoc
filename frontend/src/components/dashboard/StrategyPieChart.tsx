"use client";

import { useState, useEffect } from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import type { EvalDataPoint } from "@/lib/types";

const STRATEGY_COLORS: Record<string, string> = {
  Vectorless: "#7C3AED",
  Hybrid: "#2E75B6",
  Direct: "#6B7280",
};

interface StrategyPieChartProps {
  latestDataPoint: EvalDataPoint | null;
  isLoading: boolean;
}

interface TooltipPayload {
  name: string;
  value: number;
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: TooltipPayload }[];
}) {
  if (!active || !payload?.length) return null;
  const { name, value } = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 shadow-lg text-[12px]">
      <p className="font-medium text-foreground">
        {name}:{" "}
        <span className="font-mono font-semibold">{(value * 100).toFixed(1)}%</span>
      </p>
    </div>
  );
}

function CustomLegend({ payload }: { payload?: { value: string; color: string }[] }) {
  if (!payload) return null;
  return (
    <div className="flex flex-col gap-1.5 mt-2">
      {payload.map((entry) => (
        <div key={entry.value} className="flex items-center gap-2">
          <span
            className="h-2.5 w-2.5 rounded-full shrink-0"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-[12px] text-muted-foreground">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

export function StrategyPieChart({
  latestDataPoint,
  isLoading,
}: StrategyPieChartProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  if (isLoading || !mounted) {
    return <Skeleton className="h-[220px] w-full rounded-lg" />;
  }

  if (!latestDataPoint) {
    return (
      <div className="h-[220px] flex items-center justify-center">
        <p className="text-sm text-muted-foreground">No data available.</p>
      </div>
    );
  }

  const pieData = [
    { name: "Vectorless", value: latestDataPoint.vectorless_pct },
    { name: "Hybrid", value: latestDataPoint.hybrid_pct },
    { name: "Direct", value: latestDataPoint.direct_pct },
  ].filter((d) => d.value > 0);

  if (pieData.length === 0) {
    return (
      <div className="h-[220px] flex items-center justify-center">
        <p className="text-sm text-muted-foreground">No strategy data.</p>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4 h-[220px]">
      <ResponsiveContainer width="60%" height="100%">
        <PieChart>
          <Pie
            data={pieData}
            cx="50%"
            cy="50%"
            innerRadius="55%"
            outerRadius="80%"
            paddingAngle={3}
            dataKey="value"
            stroke="none"
          >
            {pieData.map((entry) => (
              <Cell
                key={entry.name}
                fill={STRATEGY_COLORS[entry.name] ?? "#6B7280"}
              />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
        </PieChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex flex-col gap-2">
        {pieData.map((entry) => (
          <div key={entry.name} className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 rounded-full shrink-0"
              style={{ backgroundColor: STRATEGY_COLORS[entry.name] ?? "#6B7280" }}
            />
            <div>
              <p className="text-[12px] font-medium text-foreground">
                {entry.name}
              </p>
              <p className="text-[11px] font-mono text-muted-foreground">
                {(entry.value * 100).toFixed(1)}%
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
