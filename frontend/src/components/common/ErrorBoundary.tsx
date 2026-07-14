"use client";

import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary]", error, info);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="flex min-h-[200px] flex-col items-center justify-center gap-4 rounded-xl border border-danger/30 bg-danger/5 p-8 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-danger/10">
            <AlertTriangle className="h-5 w-5 text-danger" />
          </div>
          <div>
            <h3 className="font-medium text-foreground">Something went wrong</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {this.state.error?.message ?? "An unexpected error occurred."}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Reload
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
