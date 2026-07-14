"use client";

import { useState, useEffect, useDeferredValue } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Search,
  FileText,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { DocumentCard } from "@/components/documents/DocumentCard";
import { DocumentUploader } from "@/components/documents/DocumentUploader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import api from "@/lib/api/findoc";
import type { FilingType } from "@/lib/types";
import { cn } from "@/lib/utils";

// ─── Filter constants ─────────────────────────────────────────────────────────

const FILING_FILTERS = [
  { value: "all", label: "All" },
  { value: "10-K", label: "10-K" },
  { value: "10-Q", label: "10-Q" },
  { value: "8-K", label: "8-K" },
  { value: "DEF14A", label: "DEF 14A" },
  { value: "OTHER", label: "Other" },
] as const;

const SORT_OPTIONS = [
  { value: "date_desc", label: "Newest first" },
  { value: "date_asc", label: "Oldest first" },
  { value: "name", label: "Name (A–Z)" },
] as const;

// ─── DocumentsView ────────────────────────────────────────────────────────────

export function DocumentsView() {
  const queryClient = useQueryClient();
  const [uploaderOpen, setUploaderOpen] = useState(false);
  const [filingType, setFilingType] = useState<"all" | FilingType>("all");
  const [sort, setSort] = useState<"date_desc" | "date_asc" | "name">(
    "date_desc"
  );
  const [search, setSearch] = useState("");
  const [isLoadingSample, setIsLoadingSample] = useState(false);

  const deferredSearch = useDeferredValue(search);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["documents", { filingType, sort, search: deferredSearch }],
    queryFn: () =>
      api.listDocuments({
        filing_type: filingType === "all" ? undefined : filingType,
        sort,
        search: deferredSearch || undefined,
      }),
    staleTime: 30_000,
  });

  const documents = data?.items ?? [];

  // Poll every 5 s while any document is processing
  const hasProcessing = documents.some((d) => d.status === "processing");
  useEffect(() => {
    if (!hasProcessing) return;
    const timer = setInterval(() => refetch(), 5_000);
    return () => clearInterval(timer);
  }, [hasProcessing, refetch]);

  const handleLoadSample = async () => {
    setIsLoadingSample(true);
    try {
      await api.loadSampleDocument();
      toast.success("Sample document loaded — ingestion started.");
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load sample.");
    } finally {
      setIsLoadingSample(false);
    }
  };

  const hasFilters = filingType !== "all" || !!deferredSearch;
  const clearFilters = () => {
    setFilingType("all");
    setSearch("");
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
          {/* ── Header ────────────────────────────────────────────────────── */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <h1 className="text-xl font-semibold text-foreground">
                Documents
              </h1>
              {data && (
                <p className="text-sm text-muted-foreground mt-0.5">
                  {data.total} document{data.total !== 1 ? "s" : ""}
                </p>
              )}
            </div>

            <Button
              onClick={() => setUploaderOpen(true)}
              className="bg-[#1F4E79] hover:bg-[#1F4E79]/90 text-white gap-2 shrink-0"
            >
              <Plus className="h-4 w-4" />
              Add Document
            </Button>
          </div>

          {/* ── Filter bar ────────────────────────────────────────────────── */}
          <div className="flex items-center gap-3 flex-wrap">
            {/* Search */}
            <div className="relative min-w-[180px] max-w-[300px] flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
              <Input
                placeholder="Search documents…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 h-9 text-sm"
              />
            </div>

            {/* Filing type pills */}
            <div className="flex items-center gap-1 flex-wrap">
              {FILING_FILTERS.map((f) => (
                <button
                  key={f.value}
                  type="button"
                  onClick={() =>
                    setFilingType(f.value as "all" | FilingType)
                  }
                  className={cn(
                    "px-3 py-1 text-[12px] font-medium rounded-full border transition-colors",
                    filingType === f.value
                      ? "border-[#1F4E79] bg-[#1F4E79]/10 text-[#1F4E79]"
                      : "border-border text-muted-foreground hover:text-foreground hover:border-muted-foreground/40"
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {/* Sort */}
            <Select
              value={sort}
              onValueChange={(v) => setSort(v as typeof sort)}
            >
              <SelectTrigger className="h-9 w-[160px] text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SORT_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value} className="text-sm">
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* ── Content area ──────────────────────────────────────────────── */}
          {isLoading ? (
            <DocumentGridSkeleton />
          ) : isError ? (
            <ErrorState onRetry={() => refetch()} />
          ) : documents.length === 0 ? (
            <EmptyState
              hasFilters={hasFilters}
              onClearFilters={clearFilters}
              onLoadSample={handleLoadSample}
              isLoadingSample={isLoadingSample}
              onUpload={() => setUploaderOpen(true)}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {documents.map((doc) => (
                <DocumentCard key={doc.id} doc={doc} />
              ))}
            </div>
          )}
        </div>
      </div>

      <DocumentUploader
        open={uploaderOpen}
        onClose={() => setUploaderOpen(false)}
      />
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function DocumentGridSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border p-5 space-y-3">
          <div className="flex items-center justify-between">
            <Skeleton className="h-5 w-16 rounded-full" />
            <Skeleton className="h-5 w-20 rounded-full" />
          </div>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <div className="flex gap-3 pt-1">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-3 w-14" />
          </div>
          <div className="flex gap-2 pt-2">
            <Skeleton className="h-7 flex-1" />
            <Skeleton className="h-7 w-7" />
            <Skeleton className="h-7 w-7" />
          </div>
        </div>
      ))}
    </div>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
      <div className="h-12 w-12 rounded-full bg-danger/10 flex items-center justify-center">
        <RefreshCw className="h-6 w-6 text-danger/70" />
      </div>
      <p className="text-sm font-medium text-foreground">
        Failed to load documents
      </p>
      <p className="text-xs text-muted-foreground">
        Check your connection and try again.
      </p>
      <Button variant="outline" size="sm" onClick={onRetry} className="mt-1">
        Retry
      </Button>
    </div>
  );
}

interface EmptyStateProps {
  hasFilters: boolean;
  onClearFilters: () => void;
  onLoadSample: () => void;
  isLoadingSample: boolean;
  onUpload: () => void;
}

function EmptyState({
  hasFilters,
  onClearFilters,
  onLoadSample,
  isLoadingSample,
  onUpload,
}: EmptyStateProps) {
  if (hasFilters) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
        <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center">
          <Search className="h-6 w-6 text-muted-foreground" />
        </div>
        <p className="text-sm font-medium text-foreground">
          No documents match your filters
        </p>
        <Button variant="outline" size="sm" onClick={onClearFilters}>
          Clear filters
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center gap-5 py-24 text-center">
      <div className="h-16 w-16 rounded-2xl bg-muted flex items-center justify-center">
        <FileText className="h-8 w-8 text-muted-foreground/60" />
      </div>
      <div className="space-y-1.5">
        <p className="text-base font-semibold text-foreground">
          No documents yet
        </p>
        <p className="text-sm text-muted-foreground max-w-[300px] leading-relaxed">
          Upload SEC filings or fetch them from EDGAR to start asking
          questions.
        </p>
      </div>
      <div className="flex items-center gap-3 flex-wrap justify-center">
        <Button
          variant="outline"
          onClick={onLoadSample}
          disabled={isLoadingSample}
          className="gap-2"
        >
          {isLoadingSample ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <FileText className="h-4 w-4" />
          )}
          Load sample documents
        </Button>
        <Button
          onClick={onUpload}
          className="bg-[#1F4E79] hover:bg-[#1F4E79]/90 text-white gap-2"
        >
          <Plus className="h-4 w-4" />
          Add Document
        </Button>
      </div>
    </div>
  );
}
