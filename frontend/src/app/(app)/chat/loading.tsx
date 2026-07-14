import { Skeleton } from "@/components/ui/skeleton";

export default function ChatLoading() {
  return (
    <div className="flex h-full flex-col">
      {/* Message list skeleton */}
      <div className="flex-1 overflow-hidden px-6 py-6 space-y-6">
        {/* Assistant message */}
        <div className="flex gap-3 max-w-3xl">
          <Skeleton className="h-6 w-6 rounded-full shrink-0 mt-0.5" />
          <div className="space-y-2 flex-1">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-4/6" />
          </div>
        </div>
        {/* User message */}
        <div className="flex justify-end">
          <Skeleton className="h-10 w-64 rounded-2xl" />
        </div>
        {/* Assistant message */}
        <div className="flex gap-3 max-w-3xl">
          <Skeleton className="h-6 w-6 rounded-full shrink-0 mt-0.5" />
          <div className="space-y-2 flex-1">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        </div>
      </div>
      {/* Input skeleton */}
      <div className="border-t border-border px-4 py-3">
        <Skeleton className="h-[52px] w-full rounded-xl" />
      </div>
    </div>
  );
}
