"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useQuery } from "@tanstack/react-query";
import {
  MessageSquare,
  FileText,
  Moon,
  Sun,
  Plus,
  ArrowRight,
  Upload,
} from "lucide-react";

import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandSeparator,
} from "@/components/ui/command";
import { useUIStore } from "@/lib/stores/uiStore";
import api from "@/lib/api/findoc";
import { cn } from "@/lib/utils";

function HighlightMatch({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <span>{text}</span>;
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
  const parts = text.split(regex);
  return (
    <span>
      {parts.map((part, i) =>
        regex.test(part) ? (
          <mark key={i} className="bg-[#7C3AED]/20 text-[#7C3AED] rounded-[2px] px-px">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </span>
  );
}

export function CommandPalette() {
  const { commandPaletteOpen, setCommandPaletteOpen } = useUIStore();
  const { resolvedTheme, setTheme } = useTheme();
  const router = useRouter();
  const [search, setSearch] = useState("");

  // Fetch on open
  const { data: conversations } = useQuery({
    queryKey: ["conversations", "recent"],
    queryFn: () => api.listConversations(5),
    enabled: commandPaletteOpen,
    staleTime: 0,
  });

  const { data: documents } = useQuery({
    queryKey: ["documents", "recent"],
    queryFn: () => api.listDocuments({ page_size: 5, sort: "date_desc" }),
    enabled: commandPaletteOpen,
    staleTime: 0,
  });

  // Global Cmd+K
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [setCommandPaletteOpen]);

  const runCommand = useCallback(
    (fn: () => void) => {
      setCommandPaletteOpen(false);
      setSearch("");
      // slight delay so dialog closes before navigation
      setTimeout(fn, 50);
    },
    [setCommandPaletteOpen]
  );

  const handleClose = (open: boolean) => {
    setCommandPaletteOpen(open);
    if (!open) setSearch("");
  };

  return (
    <CommandDialog open={commandPaletteOpen} onOpenChange={handleClose}>
      <CommandInput
        placeholder="Search conversations, documents, actions..."
        value={search}
        onValueChange={setSearch}
        aria-label="Command palette search"
      />

      <CommandList>
        <CommandEmpty>No results for &ldquo;{search}&rdquo;</CommandEmpty>

        {/* Actions */}
        <CommandGroup heading="Actions">
          <CommandItem
            value="new chat create conversation"
            onSelect={() =>
              runCommand(async () => {
                try {
                  const convo = await api.createConversation([]);
                  router.push(`/chat/${convo.id}`);
                } catch {
                  router.push("/chat");
                }
              })
            }
          >
            <Plus className="text-muted-foreground" />
            <span>New chat</span>
            <span className="ml-auto text-xs text-muted-foreground">↵</span>
          </CommandItem>

          <CommandItem
            value="upload document file"
            onSelect={() => runCommand(() => router.push("/documents"))}
          >
            <Upload className="text-muted-foreground" />
            <span>Upload document</span>
          </CommandItem>

          <CommandItem
            value="toggle dark light mode theme"
            onSelect={() =>
              runCommand(() =>
                setTheme(resolvedTheme === "dark" ? "light" : "dark")
              )
            }
          >
            {resolvedTheme === "dark" ? (
              <Sun className="text-muted-foreground" />
            ) : (
              <Moon className="text-muted-foreground" />
            )}
            <span>
              Switch to {resolvedTheme === "dark" ? "light" : "dark"} mode
            </span>
          </CommandItem>
        </CommandGroup>

        {/* Recent conversations */}
        {conversations && conversations.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Recent conversations">
              {conversations.map((conv) => (
                <CommandItem
                  key={conv.id}
                  value={conv.title || `conversation ${conv.id}`}
                  onSelect={() =>
                    runCommand(() => router.push(`/chat/${conv.id}`))
                  }
                >
                  <MessageSquare className="text-muted-foreground shrink-0" />
                  <span className="truncate flex-1">
                    <HighlightMatch
                      text={conv.title || "Untitled conversation"}
                      query={search}
                    />
                  </span>
                  <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0 opacity-0 group-data-[selected=true]:opacity-100 transition-opacity" />
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}

        {/* Documents */}
        {documents && documents.items.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Documents">
              {documents.items.map((doc) => (
                <CommandItem
                  key={doc.id}
                  value={`${doc.name} ${doc.ticker ?? ""} ${doc.filing_type}`}
                  onSelect={() =>
                    runCommand(() => router.push("/documents"))
                  }
                >
                  <FileText className="text-muted-foreground shrink-0" />
                  <div className="flex flex-col gap-0 flex-1 min-w-0">
                    <span className="truncate text-sm leading-tight">
                      <HighlightMatch text={doc.name} query={search} />
                    </span>
                    <span className="text-[11px] text-muted-foreground leading-tight">
                      {doc.filing_type}
                      {doc.ticker && ` · ${doc.ticker}`}
                    </span>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}
      </CommandList>

      {/* Footer hint */}
      <div className="flex items-center justify-between border-t border-border px-3 py-2">
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-border bg-muted px-1 font-mono">↑↓</kbd>
            navigate
          </span>
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-border bg-muted px-1 font-mono">↵</kbd>
            select
          </span>
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-border bg-muted px-1 font-mono">esc</kbd>
            close
          </span>
        </div>
      </div>
    </CommandDialog>
  );
}
