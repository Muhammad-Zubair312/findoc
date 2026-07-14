"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Bell, Plus, Search, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useUIStore } from "@/lib/stores/uiStore";
import { useAuth } from "@/lib/hooks/useAuth";
import api from "@/lib/api/findoc";
import { cn } from "@/lib/utils";

interface Breadcrumb {
  label: string;
  href?: string;
}

const PAGE_META: Record<string, { title: string; breadcrumbs?: Breadcrumb[] }> = {
  "/chat": { title: "Chat" },
  "/documents": { title: "Documents" },
  "/dashboard": { title: "Dashboard" },
  "/settings": { title: "Settings" },
};

function getPageMeta(pathname: string) {
  if (pathname.startsWith("/chat/")) {
    return {
      title: "Chat",
      breadcrumbs: [
        { label: "Chat", href: "/chat" },
        { label: "Conversation" },
      ],
    };
  }
  return PAGE_META[pathname] ?? { title: "FinDoc" };
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function TopBar() {
  const pathname = usePathname();
  const router = useRouter();
  const { setCommandPaletteOpen } = useUIStore();
  const { user } = useAuth();
  const [scrolled, setScrolled] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const pageMeta = getPageMeta(pathname);

  // Track scroll on the main content area
  useEffect(() => {
    const main = document.querySelector("main");
    if (!main) return;
    const handleScroll = () => setScrolled(main.scrollTop > 4);
    main.addEventListener("scroll", handleScroll, { passive: true });
    return () => main.removeEventListener("scroll", handleScroll);
  }, [pathname]);

  const handleNewChat = async () => {
    if (isCreating) return;
    setIsCreating(true);
    try {
      const convo = await api.createConversation([]);
      router.push(`/chat/${convo.id}`);
    } catch {
      router.push("/chat");
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <header
      className={cn(
        "sticky top-0 z-20 flex h-[60px] shrink-0 items-center gap-4 border-b border-border px-4 transition-all duration-200",
        scrolled
          ? "bg-background/80 backdrop-blur-md shadow-sm"
          : "bg-background"
      )}
    >
      {/* Left: title + breadcrumb */}
      <div className="flex items-center gap-1.5 min-w-0">
        {pageMeta.breadcrumbs ? (
          <nav aria-label="Breadcrumb" className="flex items-center gap-1">
            {pageMeta.breadcrumbs.map((crumb, i) => (
              <span key={i} className="flex items-center gap-1">
                {i > 0 && (
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                )}
                {crumb.href ? (
                  <a
                    href={crumb.href}
                    className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {crumb.label}
                  </a>
                ) : (
                  <span className="text-sm font-medium text-foreground truncate max-w-[200px]">
                    {crumb.label}
                  </span>
                )}
              </span>
            ))}
          </nav>
        ) : (
          <h1 className="text-sm font-semibold text-foreground">{pageMeta.title}</h1>
        )}
      </div>

      {/* Center: search / command palette trigger */}
      <button
        onClick={() => setCommandPaletteOpen(true)}
        className="flex flex-1 max-w-[360px] items-center gap-2 rounded-lg border border-input bg-muted/40 px-3 py-2 text-sm text-muted-foreground hover:bg-muted/70 hover:text-foreground transition-all duration-150 mx-auto"
        aria-label="Open command palette (⌘K)"
      >
        <Search className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="flex-1 text-left text-[13px]">Search or jump to...</span>
        <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-border/60 bg-background/60 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground/70">
          ⌘K
        </kbd>
      </button>

      {/* Right: actions */}
      <div className="flex items-center gap-2 ml-auto">
        <Button
          variant="purple"
          size="sm"
          onClick={handleNewChat}
          disabled={isCreating}
          className="hidden sm:inline-flex gap-1.5"
          aria-label="Start new chat"
        >
          <Plus className="h-3.5 w-3.5" />
          New Chat
        </Button>

        <Button
          variant="ghost"
          size="icon"
          aria-label="Notifications"
          className="text-muted-foreground hover:text-foreground h-8 w-8"
        >
          <Bell className="h-[15px] w-[15px]" />
        </Button>

        {user && (
          <Avatar className="h-7 w-7">
            {user.avatar_url && (
              <AvatarImage src={user.avatar_url} alt={user.full_name} />
            )}
            <AvatarFallback className="text-[10px]">
              {getInitials(user.full_name)}
            </AvatarFallback>
          </Avatar>
        )}
      </div>
    </header>
  );
}
