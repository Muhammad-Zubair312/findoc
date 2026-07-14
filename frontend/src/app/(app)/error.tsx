"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, RotateCcw, Home } from "lucide-react";
import { Button } from "@/components/ui/button";

interface AppErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function AppError({ error, reset }: AppErrorProps) {
  const router = useRouter();

  useEffect(() => {
    console.error("[AppError]", error);
  }, [error]);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-5 p-6 text-center bg-background">
      <div className="h-14 w-14 rounded-full bg-danger/10 flex items-center justify-center">
        <AlertCircle className="h-7 w-7 text-danger" />
      </div>

      <div className="space-y-2 max-w-[340px]">
        <h2 className="text-lg font-semibold text-foreground">
          Something went wrong
        </h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {error.message || "An unexpected error occurred in this section."}
        </p>
        {error.digest && (
          <p className="text-[11px] font-mono text-muted-foreground/60 mt-1">
            Error ID: {error.digest}
          </p>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Button
          onClick={reset}
          className="gap-2 bg-[#1F4E79] hover:bg-[#1F4E79]/90 text-white"
          size="sm"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Try again
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => router.push("/chat")}
          className="gap-2"
        >
          <Home className="h-3.5 w-3.5" />
          Go to Chat
        </Button>
      </div>
    </div>
  );
}
