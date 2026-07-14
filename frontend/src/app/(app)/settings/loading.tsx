import { Skeleton } from "@/components/ui/skeleton";

export default function SettingsLoading() {
  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-48 border-r border-border p-4 space-y-1">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
      {/* Content */}
      <div className="flex-1 p-6 space-y-6 max-w-2xl">
        <Skeleton className="h-6 w-32" />
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="space-y-1.5">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-9 w-full" />
            </div>
          ))}
        </div>
        <Skeleton className="h-9 w-32" />
      </div>
    </div>
  );
}
