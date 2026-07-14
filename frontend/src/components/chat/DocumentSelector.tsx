"use client";

import { FileText, ChevronDown, X } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Checkbox } from "@/components/ui/checkbox";
import { useDocuments } from "@/lib/hooks/useDocuments";
import { useChatStore } from "@/lib/stores/chatStore";
import { cn } from "@/lib/utils";

export function DocumentSelector() {
  const { data } = useDocuments();
  const { selectedDocumentIds, addSelectedDocument, removeSelectedDocument, setSelectedDocuments } =
    useChatStore();

  const documents = data?.items ?? [];
  const count = selectedDocumentIds.length;

  const label =
    count === 0
      ? "All documents"
      : count === 1
      ? (documents.find((d) => d.id === selectedDocumentIds[0])?.ticker ??
         documents.find((d) => d.id === selectedDocumentIds[0])?.name.slice(0, 20) ??
         "1 document")
      : `${count} documents`;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(
            "flex items-center gap-1.5 rounded-full border border-input bg-background px-3 py-1.5 text-xs transition-colors duration-150",
            "hover:border-[#7C3AED]/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            count > 0
              ? "border-[#7C3AED]/40 text-[#7C3AED] bg-[#7C3AED]/5"
              : "text-muted-foreground"
          )}
          aria-label="Select documents to query"
        >
          <FileText className="h-3 w-3 shrink-0" />
          <span className="max-w-[140px] truncate font-medium">{label}</span>
          <ChevronDown className="h-3 w-3 shrink-0 opacity-60" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="start" className="w-72" sideOffset={6}>
        <DropdownMenuLabel className="flex items-center justify-between">
          <span>Scope to documents</span>
          {count > 0 && (
            <button
              type="button"
              onClick={() => setSelectedDocuments([])}
              className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1"
            >
              <X className="h-3 w-3" />
              Clear
            </button>
          )}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        {documents.length === 0 ? (
          <div className="py-6 text-center text-xs text-muted-foreground">
            No documents uploaded yet
          </div>
        ) : (
          documents.map((doc) => {
            const selected = selectedDocumentIds.includes(doc.id);
            return (
              <DropdownMenuItem
                key={doc.id}
                onSelect={(e) => {
                  e.preventDefault();
                  if (selected) {
                    removeSelectedDocument(doc.id);
                  } else {
                    addSelectedDocument(doc.id);
                  }
                }}
                className="flex items-center gap-2.5 cursor-pointer"
              >
                <Checkbox
                  checked={selected}
                  onCheckedChange={() => {}}
                  tabIndex={-1}
                  className="pointer-events-none"
                />
                <div className="flex flex-col min-w-0">
                  <span className="truncate text-sm font-medium">{doc.name}</span>
                  <span className="text-[11px] text-muted-foreground">
                    {doc.filing_type}
                    {doc.ticker && ` · ${doc.ticker}`}
                    {doc.status === "processing" && " · indexing..."}
                  </span>
                </div>
              </DropdownMenuItem>
            );
          })
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
