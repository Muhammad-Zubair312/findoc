"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Trash2, MessageSquare } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip";
import { useChatStore } from "@/lib/stores/chatStore";
import api from "@/lib/api/findoc";
import type { Document, FilingType } from "@/lib/types";
import { cn } from "@/lib/utils";
import { format } from "date-fns";

// ─── Styling maps ─────────────────────────────────────────────────────────────

const FILING_COLORS: Record<FilingType, { bg: string; text: string }> = {
  "10-K": { bg: "bg-[#2E75B6]/15", text: "text-[#2E75B6]" },
  "10-Q": { bg: "bg-[#7C3AED]/15", text: "text-[#7C3AED]" },
  "8-K": { bg: "bg-warning/15", text: "text-warning" },
  "DEF14A": { bg: "bg-success/15", text: "text-success" },
  "OTHER": { bg: "bg-muted", text: "text-muted-foreground" },
};

const STATUS_CONFIG = {
  indexed: { dot: "bg-success", label: "Indexed" },
  processing: { dot: "bg-warning animate-pulse", label: "Processing" },
  failed: { dot: "bg-danger", label: "Failed" },
} as const;

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// ─── DocumentCard ─────────────────────────────────────────────────────────────

interface DocumentCardProps {
  doc: Document;
}

export function DocumentCard({ doc }: DocumentCardProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { setSelectedDocuments } = useChatStore();

  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isReingesting, setIsReingesting] = useState(false);

  const filingColor = FILING_COLORS[doc.filing_type] ?? FILING_COLORS.OTHER;
  const statusCfg = STATUS_CONFIG[doc.status];

  const handleSelectForChat = useCallback(() => {
    setSelectedDocuments([doc.id]);
    router.push("/chat");
  }, [doc.id, setSelectedDocuments, router]);

  const handleReingest = useCallback(async () => {
    setIsReingesting(true);
    try {
      await api.reingestDocument(doc.id);
      toast.success("Re-ingestion started.");
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    } catch {
      toast.error("Failed to start re-ingestion.");
    } finally {
      setIsReingesting(false);
    }
  }, [doc.id, queryClient]);

  const handleDelete = useCallback(async () => {
    setIsDeleting(true);
    try {
      await api.deleteDocument(doc.id);
      toast.success("Document deleted.");
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    } catch {
      toast.error("Failed to delete document.");
      setIsDeleting(false);
      setIsConfirmingDelete(false);
    }
  }, [doc.id, queryClient]);

  return (
    <div
      className={cn(
        "group relative rounded-xl border border-border bg-card p-5 flex flex-col gap-3",
        "hover:shadow-md hover:border-border/80 transition-all duration-150",
        isDeleting && "opacity-50 pointer-events-none"
      )}
    >
      {/* Top: filing type badge + status */}
      <div className="flex items-center justify-between">
        <span
          className={cn(
            "inline-flex items-center text-[11px] font-semibold rounded-full px-2.5 py-0.5",
            filingColor.bg,
            filingColor.text
          )}
        >
          {doc.filing_type}
        </span>
        <div className="flex items-center gap-1.5">
          <span className={cn("h-2 w-2 rounded-full shrink-0", statusCfg.dot)} />
          <span className="text-[11px] text-muted-foreground">{statusCfg.label}</span>
        </div>
      </div>

      {/* Name + filer */}
      <div>
        <p
          className="text-[14px] font-semibold text-foreground leading-snug line-clamp-2"
          title={doc.name}
        >
          {doc.name}
        </p>
        <p className="text-[12px] text-muted-foreground mt-0.5 truncate">
          {doc.filer_name}
          {doc.ticker ? ` · ${doc.ticker}` : ""}
        </p>
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-3 flex-wrap">
        {doc.filing_date && (
          <span className="text-[11px] text-muted-foreground">
            {format(new Date(doc.filing_date), "MMM d, yyyy")}
          </span>
        )}
        {doc.page_count != null && (
          <span className="text-[11px] text-muted-foreground">
            {doc.page_count}p
          </span>
        )}
        {doc.node_count != null && (
          <span className="text-[11px] text-muted-foreground">
            {doc.node_count} nodes
          </span>
        )}
        {doc.file_size_bytes != null && (
          <span className="text-[11px] text-muted-foreground">
            {formatBytes(doc.file_size_bytes)}
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="mt-auto pt-1">
        {isConfirmingDelete ? (
          <div className="flex items-center gap-2">
            <span className="text-[12px] text-danger font-medium flex-1">
              Delete this document?
            </span>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2.5 text-xs"
              onClick={() => setIsConfirmingDelete(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              className="h-7 px-2.5 text-xs"
              onClick={handleDelete}
            >
              Delete
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs gap-1.5 flex-1 min-w-0"
              onClick={handleSelectForChat}
              disabled={doc.status !== "indexed"}
            >
              <MessageSquare className="h-3 w-3 shrink-0" />
              <span className="truncate">Select for Chat</span>
            </Button>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 shrink-0 text-muted-foreground hover:text-foreground"
                    onClick={handleReingest}
                    disabled={isReingesting || doc.status === "processing"}
                    aria-label="Re-ingest document"
                  >
                    <RotateCcw
                      className={cn(
                        "h-3.5 w-3.5",
                        isReingesting && "animate-spin"
                      )}
                    />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Re-ingest</TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 shrink-0 text-muted-foreground hover:text-danger transition-colors"
                    onClick={() => setIsConfirmingDelete(true)}
                    aria-label="Delete document"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Delete</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        )}
      </div>
    </div>
  );
}
