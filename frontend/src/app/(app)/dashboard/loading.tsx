import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardLoading() {
  return (
    <div className="p-6 space-y-6 overflow-auto h-full">
      {/* Metric cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-border p-5 space-y-3">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="h-10 w-20" />
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
      </div>
      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-border p-5 space-y-4">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-[200px] w-full" />
        </div>
        <div className="rounded-xl border border-border p-5 space-y-4">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-[200px] w-full" />
        </div>
      </div>
      {/* Table */}
      <div className="rounded-xl border border-border p-5 space-y-4">
        <Skeleton className="h-4 w-48" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}
