"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/hooks/useAuth";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  // If already authenticated, bounce to the app
  useEffect(() => {
    if (!isLoading && user) {
      router.replace("/chat");
    }
  }, [user, isLoading, router]);

  // Render form immediately — the effect handles redirect silently
  return <>{children}</>;
}
