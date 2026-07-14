"use client";

import { useRef, useEffect, useState, useCallback, useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  FileText,
  AlertCircle,
  Database,
  Calendar,
  Hash,
  BarChart3,
  FileCode,
  MessageSquare,
  Tag,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TreeView } from "@/components/documents/TreeView";
import { CitationCard } from "@/components/citations/CitationCard";
import { Skeleton } from "@/components/ui/skeleton";
import api from "@/lib/api/findoc";
import { useUIStore } from "@/lib/stores/uiStore";
import { useChatStore } from "@/lib/stores/chatStore";
import type { Citation, Document, TreeNode } from "@/lib/types";
import { cn } from "@/lib/utils";
import { format } from "date-fns";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// ─── Modal content type ───────────────────────────────────────────────────────

type ModalContent =
  | { type: "node"; node: TreeNode }
  | { type: "citation"; citation: Citation; index: number }
  | null;

// ─── SourceTreePanel ──────────────────────────────────────────────────────────

interface SourceTreePanelProps {
  selectedDocumentIds: string[];
}

export function SourceTreePanel({ selectedDocumentIds }: SourceTreePanelProps) {
  const { activeSourceTab, setActiveSourceTab } = useUIStore();
  const { streaming, isStreaming, conversations, activeConversationId } =
    useChatStore();

  // Derive messages and citations
  const messages = activeConversationId
    ? (conversations[activeConversationId] ?? [])
    : [];
  const lastAssistantMsg = useMemo(
    () => [...messages].reverse().find((m) => m.role === "assistant"),
    [messages]
  );
  const displayCitations = useMemo<Citation[]>(
    () =>
      isStreaming
        ? streaming.citations
        : (lastAssistantMsg?.citations ?? []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [isStreaming, streaming.citations, lastAssistantMsg?.citations]
  );

  // Active document for tree/metadata (user can change via selector)
  const [activeTreeDocId, setActiveTreeDocId] = useState<string>(
    () => selectedDocumentIds[0] ?? ""
  );

  useEffect(() => {
    if (
      !selectedDocumentIds.includes(activeTreeDocId) &&
      selectedDocumentIds.length > 0
    ) {
      setActiveTreeDocId(selectedDocumentIds[0]);
    }
  }, [selectedDocumentIds, activeTreeDocId]);

  // Fetch tree — always enabled so nodes are ready before user switches tab
  const {
    data: treeNodes,
    isLoading: isTreeLoading,
    isError: isTreeError,
  } = useQuery({
    queryKey: ["tree", activeTreeDocId],
    queryFn: () => api.getDocumentTree(activeTreeDocId),
    enabled: !!activeTreeDocId,
    staleTime: 30_000,
  });

  // Fetch document metadata — lazy (only on metadata tab)
  const { data: docMeta, isLoading: isMetaLoading } = useQuery({
    queryKey: ["document", activeTreeDocId],
    queryFn: () => api.getDocument(activeTreeDocId),
    enabled: !!activeTreeDocId && activeSourceTab === "metadata",
    staleTime: 30_000,
  });

  // Document names for selector dropdown
  const { data: allDocs } = useQuery({
    queryKey: ["documents", "panel-names"],
    queryFn: () => api.listDocuments({ page_size: 100 }),
    enabled: selectedDocumentIds.length > 1,
    staleTime: 30_000,
  });

  const docNameMap = useMemo(() => {
    const m: Record<string, string> = {};
    (allDocs?.items ?? []).forEach((d) => { m[d.id] = d.name; });
    return m;
  }, [allDocs]);

  // Referenced node IDs for tree highlighting
  const referencedNodeIds = useMemo(() => {
    const ids = new Set<string>();
    displayCitations.forEach((c) => {
      if (c.document_id === activeTreeDocId) ids.add(c.node_id);
    });
    return ids;
  }, [displayCitations, activeTreeDocId]);

  // Cross-tab hover state
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  // Auto-tab-switch with user-override guard
  const userManuallySwitched = useRef(false);
  const prevCitationsLength = useRef(0);

  useEffect(() => {
    if (isStreaming) {
      userManuallySwitched.current = false;
      prevCitationsLength.current = 0;
    }
  }, [isStreaming]);

  useEffect(() => {
    const len = displayCitations.length;
    if (
      len > 0 &&
      prevCitationsLength.current === 0 &&
      !userManuallySwitched.current
    ) {
      setActiveSourceTab("citations");
    }
    prevCitationsLength.current = len;
  }, [displayCitations.length, setActiveSourceTab]);

  const handleTabClick = useCallback(
    (tab: "tree" | "citations" | "metadata") => {
      if (isStreaming) userManuallySwitched.current = true;
      setActiveSourceTab(tab);
    },
    [isStreaming, setActiveSourceTab]
  );

  // Preview modal
  const [modalContent, setModalContent] = useState<ModalContent>(null);

  // Ref passed to TreeView for auto-scroll
  const treeScrollRef = useRef<HTMLDivElement>(null);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 px-4 pt-4 pb-2 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[13px] font-semibold text-foreground tracking-wide uppercase">
            Sources
          </span>
        </div>

        {selectedDocumentIds.length > 1 && (
          <Select value={activeTreeDocId} onValueChange={setActiveTreeDocId}>
            <SelectTrigger className="h-7 text-xs">
              <SelectValue placeholder="Select document" />
            </SelectTrigger>
            <SelectContent>
              {selectedDocumentIds.map((id) => (
                <SelectItem key={id} value={id} className="text-xs">
                  {docNameMap[id] ?? `${id.slice(0, 8)}…`}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Tab bar */}
      <div className="shrink-0 flex border-b border-border px-2 pt-1">
        {(["tree", "citations", "metadata"] as const).map((tab) => {
          const labels: Record<string, string> = {
            tree: "Tree",
            citations: "Citations",
            metadata: "Details",
          };
          const isActive = activeSourceTab === tab;
          const badge =
            tab === "citations" && displayCitations.length > 0
              ? displayCitations.length
              : null;

          return (
            <button
              key={tab}
              type="button"
              onClick={() => handleTabClick(tab)}
              className={cn(
                "relative flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium transition-colors select-none",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-t-md",
                isActive
                  ? "text-[#7C3AED] border-b-2 border-[#7C3AED] -mb-px"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {labels[tab]}
              {badge !== null && (
                <span className="inline-flex items-center justify-center h-4 min-w-[1rem] px-1 text-[10px] font-mono rounded-full bg-[#7C3AED]/15 text-[#7C3AED]">
                  {badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab content — all mounted, CSS show/hide for scroll preservation */}
      <div className="flex-1 overflow-hidden relative">
        {/* Tree */}
        <div
          className={cn(
            "absolute inset-0",
            activeSourceTab !== "tree" && "hidden"
          )}
        >
          {isTreeError ? (
            <PanelError message="Failed to load document tree." />
          ) : (
            <TreeView
              nodes={treeNodes ?? []}
              isLoading={isTreeLoading}
              referencedNodeIds={referencedNodeIds}
              hoveredNodeId={hoveredNodeId}
              onNodeDoubleClick={(node) =>
                setModalContent({ type: "node", node })
              }
              onNodeHover={setHoveredNodeId}
              scrollRef={treeScrollRef}
            />
          )}
        </div>

        {/* Citations */}
        <div
          className={cn(
            "absolute inset-0 overflow-y-auto scrollbar-thin p-3 space-y-2",
            activeSourceTab !== "citations" && "hidden"
          )}
        >
          {displayCitations.length === 0 ? (
            <CitationsEmpty isStreaming={isStreaming} />
          ) : (
            displayCitations.map((citation, i) => (
              <CitationCard
                key={citation.id}
                citation={citation}
                index={i}
                isHighlighted={hoveredNodeId === citation.node_id}
                onHoverEnter={() => setHoveredNodeId(citation.node_id)}
                onHoverLeave={() => setHoveredNodeId(null)}
                onReadMore={() =>
                  setModalContent({ type: "citation", citation, index: i })
                }
              />
            ))
          )}
        </div>

        {/* Metadata */}
        <div
          className={cn(
            "absolute inset-0 overflow-y-auto scrollbar-thin p-4",
            activeSourceTab !== "metadata" && "hidden"
          )}
        >
          {isMetaLoading ? (
            <MetadataSkeleton />
          ) : docMeta ? (
            <MetadataGrid doc={docMeta} />
          ) : (
            <PanelError message="Failed to load document details." />
          )}
        </div>
      </div>

      {/* Preview modal */}
      <Dialog
        open={!!modalContent}
        onOpenChange={(open) => !open && setModalContent(null)}
      >
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col overflow-hidden">
          {modalContent?.type === "node" && (
            <>
              <DialogHeader>
                <DialogTitle className="pr-8 text-base">
                  {modalContent.node.title}
                </DialogTitle>
                <DialogDescription>
                  Pages {modalContent.node.page_start}–{modalContent.node.page_end}
                </DialogDescription>
              </DialogHeader>
              <div className="flex-1 overflow-y-auto scrollbar-thin mt-2">
                <pre className="text-sm text-foreground leading-relaxed whitespace-pre-wrap font-mono bg-muted/40 rounded-lg p-4 break-words">
                  {modalContent.node.content_preview || "No preview available."}
                </pre>
              </div>
            </>
          )}
          {modalContent?.type === "citation" && (
            <>
              <DialogHeader>
                <DialogTitle className="pr-8 text-base flex items-baseline gap-2">
                  <span className="text-[11px] font-mono text-muted-foreground shrink-0">
                    [{modalContent.index + 1}]
                  </span>
                  <span>{modalContent.citation.section_title}</span>
                </DialogTitle>
                <DialogDescription>
                  {modalContent.citation.document_name} · Pages{" "}
                  {modalContent.citation.page_start}–
                  {modalContent.citation.page_end}
                </DialogDescription>
              </DialogHeader>
              <div className="flex-1 overflow-y-auto scrollbar-thin mt-2">
                <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap bg-muted/40 rounded-lg p-4">
                  {modalContent.citation.full_text || modalContent.citation.excerpt}
                </p>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function PanelError({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 h-full text-center p-6">
      <AlertCircle className="h-7 w-7 text-danger/60" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

function CitationsEmpty({ isStreaming }: { isStreaming: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center px-4">
      <MessageSquare className="h-7 w-7 text-muted-foreground/40" />
      <p className="text-sm text-muted-foreground">
        {isStreaming
          ? "Retrieving sources…"
          : "No citations for this answer."}
      </p>
    </div>
  );
}

function MetadataSkeleton() {
  return (
    <div className="space-y-3 pt-1">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex gap-3">
          <Skeleton className="h-8 w-8 rounded-md shrink-0" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3 w-24 rounded" />
            <Skeleton className="h-4 w-40 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}

interface MetaRowProps {
  icon: ReactNode;
  label: string;
  value: string;
}

function MetaRow({ icon, label, value }: MetaRowProps) {
  return (
    <div className="flex items-start gap-3 rounded-lg px-2 py-2 hover:bg-muted/50 transition-colors">
      <span className="shrink-0 mt-0.5 text-muted-foreground">{icon}</span>
      <div className="min-w-0">
        <div className="text-[11px] text-muted-foreground mb-0.5">{label}</div>
        <div className="text-[13px] text-foreground break-words">{value}</div>
      </div>
    </div>
  );
}

function MetadataGrid({ doc }: { doc: Document }) {
  const statusColor =
    doc.status === "indexed"
      ? "bg-success/10 text-success"
      : doc.status === "processing"
      ? "bg-warning/10 text-warning"
      : "bg-danger/10 text-danger";

  const statusLabel =
    doc.status === "indexed"
      ? "Indexed"
      : doc.status === "processing"
      ? "Processing"
      : "Failed";

  return (
    <div className="space-y-1">
      {/* Status badge */}
      <div className="px-2 pb-3">
        <span
          className={cn(
            "inline-flex items-center text-[11px] font-medium rounded-full px-2.5 py-0.5",
            statusColor
          )}
        >
          {statusLabel}
        </span>
      </div>

      <MetaRow
        icon={<FileText className="h-4 w-4" />}
        label="Name"
        value={doc.name}
      />
      <MetaRow
        icon={<Tag className="h-4 w-4" />}
        label="Filing type"
        value={doc.filing_type}
      />
      <MetaRow
        icon={<Hash className="h-4 w-4" />}
        label="Ticker"
        value={doc.ticker ?? "—"}
      />
      <MetaRow
        icon={<Database className="h-4 w-4" />}
        label="Filer"
        value={doc.filer_name}
      />
      <MetaRow
        icon={<Calendar className="h-4 w-4" />}
        label="Filing date"
        value={
          doc.filing_date
            ? format(new Date(doc.filing_date), "MMM d, yyyy")
            : "—"
        }
      />
      <MetaRow
        icon={<BarChart3 className="h-4 w-4" />}
        label="Pages"
        value={doc.page_count != null ? String(doc.page_count) : "—"}
      />
      <MetaRow
        icon={<FileCode className="h-4 w-4" />}
        label="Nodes"
        value={doc.node_count != null ? String(doc.node_count) : "—"}
      />
      <MetaRow
        icon={<Database className="h-4 w-4" />}
        label="File size"
        value={doc.file_size_bytes != null ? formatBytes(doc.file_size_bytes) : "—"}
      />
      <MetaRow
        icon={<Calendar className="h-4 w-4" />}
        label="Ingested"
        value={
          doc.ingested_at
            ? format(new Date(doc.ingested_at), "MMM d, yyyy 'at' h:mm a")
            : "Not yet ingested"
        }
      />
    </div>
  );
}
