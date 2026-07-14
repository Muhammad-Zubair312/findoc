"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { NavRail } from "@/components/layout/NavRail";
import { TopBar } from "@/components/layout/TopBar";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { useAuth } from "@/lib/hooks/useAuth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <LoadingSpinner size="lg" />
          <p className="text-xs text-muted-foreground">Loading FinDoc...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    /*
     * overflow-x-hidden prevents any rogue horizontal scroll on mobile.
     * The inner layout remains flex row: NavRail (sidebar) + content column.
     * NavRail should handle its own mobile visibility (e.g. hidden on mobile
     * with a bottom nav, or a hamburger drawer — depends on NavRail.tsx).
     */
    <div className="flex h-screen overflow-hidden overflow-x-hidden bg-background">
      {/* Sidebar navigation — NavRail handles its own responsive behaviour */}
      <NavRail />

      {/* Main content column */}
      <div className="flex flex-col flex-1 overflow-hidden min-w-0">
        {/* Top bar */}
        <TopBar />

        {/*
         * main: flex-1 + overflow-hidden lets each page control its own
         * scroll (e.g. DashboardView has overflow-y-auto internally,
         * ChatWindow uses a flex column with a scrollable MessageList).
         */}
        <main
          className="flex-1 overflow-hidden"
          id="main-content"
        >
          {children}
        </main>
      </div>

      {/* Global command palette (Cmd+K) */}
      <CommandPalette />
    </div>
  );
}