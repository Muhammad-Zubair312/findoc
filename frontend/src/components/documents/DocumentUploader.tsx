"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Upload,
  FileText,
  Check,
  AlertCircle,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import api from "@/lib/api/findoc";
import type { IngestionProgress, FilingType } from "@/lib/types";
import { cn } from "@/lib/utils";

// ─── Constants ────────────────────────────────────────────────────────────────

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_FILE_SIZE = 50 * 1024 * 1024;
const CURRENT_YEAR = new Date().getFullYear();

const FILING_TYPES: FilingType[] = ["10-K", "10-Q", "8-K", "DEF14A", "OTHER"];

const PHASE_STEPS = [
  { key: "parsing", label: "Parse" },
  { key: "tree-build", label: "Tree" },
  { key: "embed-fallback", label: "Embed" },
  { key: "done", label: "Done" },
] as const;

const PHASE_LABELS: Record<string, string> = {
  parsing: "Parsing document…",
  "tree-build": "Building document tree…",
  "embed-fallback": "Generating embeddings…",
  done: "Indexing complete",
  failed: "Ingestion failed",
};

type Phase = "idle" | "uploading" | "ingesting" | "done" | "error";

// ─── DocumentUploader ─────────────────────────────────────────────────────────

interface DocumentUploaderProps {
  open: boolean;
  onClose: () => void;
}

export function DocumentUploader({ open, onClose }: DocumentUploaderProps) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [phase, setPhase] = useState<Phase>("idle");
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [ingestionDocId, setIngestionDocId] = useState<string | null>(null);
  const [progress, setProgress] = useState<IngestionProgress | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // EDGAR form state
  const [ticker, setTicker] = useState("");
  const [formType, setFormType] = useState<FilingType>("10-K");
  const [year, setYear] = useState(String(CURRENT_YEAR - 1));

  // Reset all state after close animation
  useEffect(() => {
    if (!open) {
      const t = setTimeout(() => {
        setPhase("idle");
        setIsDragging(false);
        setSelectedFile(null);
        setIngestionDocId(null);
        setProgress(null);
        setErrorMessage(null);
        setTicker("");
        setFormType("10-K");
        setYear(String(CURRENT_YEAR - 1));
      }, 300);
      return () => clearTimeout(t);
    }
  }, [open]);

  // SSE ingestion progress connection
  useEffect(() => {
    if (!ingestionDocId) return;

    setPhase("ingesting");

    const es = new EventSource(`${API_URL}/documents/${ingestionDocId}/progress`, {
      withCredentials: true,
    });

    es.onmessage = (event) => {
      try {
        const data: IngestionProgress = JSON.parse(event.data as string);
        setProgress(data);

        if (data.phase === "done") {
          es.close();
          setPhase("done");
          queryClient.invalidateQueries({ queryKey: ["documents"] });
          setTimeout(() => onClose(), 2000);
        } else if (data.phase === "failed") {
          es.close();
          setPhase("error");
          setErrorMessage(data.error ?? "Ingestion failed.");
        }
      } catch {
        // ignore malformed SSE frames
      }
    };

    es.onerror = () => {
      es.close();
      setPhase((prev) => {
        if (prev === "ingesting") {
          setErrorMessage(
            "Lost connection to the ingestion stream. The document may still be processing — check the library."
          );
          return "error";
        }
        return prev;
      });
    };

    return () => es.close();
  }, [ingestionDocId, queryClient, onClose]);

  // ── File handling ─────────────────────────────────────────────────────────

  const validateFile = (file: File): string | null => {
    if (file.type !== "application/pdf") return "Only PDF files are supported.";
    if (file.size > MAX_FILE_SIZE) return "File must be under 50 MB.";
    return null;
  };

  const applyFile = (file: File) => {
    const err = validateFile(file);
    if (err) { toast.error(err); return; }
    setSelectedFile(file);
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) applyFile(file);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) applyFile(file);
      e.target.value = "";
    },
    [] // eslint-disable-line react-hooks/exhaustive-deps
  );

  // ── Submit handlers ───────────────────────────────────────────────────────

  const handleUpload = async () => {
    if (!selectedFile) return;
    setPhase("uploading");
    try {
      const result = await api.uploadDocument(selectedFile);
      setIngestionDocId(result.document_id);
    } catch (err) {
      setPhase("error");
      setErrorMessage(err instanceof Error ? err.message : "Upload failed.");
    }
  };

  const handleEdgarFetch = async () => {
    const yearNum = parseInt(year, 10);
    if (!ticker.trim()) {
      toast.error("Enter a ticker symbol.");
      return;
    }
    if (isNaN(yearNum) || yearNum < 1993 || yearNum > CURRENT_YEAR) {
      toast.error(`Year must be between 1993 and ${CURRENT_YEAR}.`);
      return;
    }
    setPhase("uploading");
    try {
      const result = await api.fetchFromEdgar({
        ticker: ticker.trim().toUpperCase(),
        form_type: formType,
        year: yearNum,
      });
      setIngestionDocId(result.document_id);
    } catch (err) {
      setPhase("error");
      setErrorMessage(
        err instanceof Error ? err.message : "EDGAR fetch failed."
      );
    }
  };

  const resetToIdle = () => {
    setPhase("idle");
    setErrorMessage(null);
    setIngestionDocId(null);
    setProgress(null);
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Document</DialogTitle>
          <DialogDescription>
            Upload a PDF or fetch directly from SEC EDGAR.
          </DialogDescription>
        </DialogHeader>

        {/* ── Form phase (idle or uploading to API) ── */}
        {(phase === "idle" || phase === "uploading") && (
          <Tabs defaultValue="upload" className="mt-1">
            <TabsList className="w-full">
              <TabsTrigger value="upload" className="flex-1">
                Upload File
              </TabsTrigger>
              <TabsTrigger value="edgar" className="flex-1">
                SEC EDGAR
              </TabsTrigger>
            </TabsList>

            {/* Upload tab */}
            <TabsContent value="upload" className="mt-4 space-y-4">
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() =>
                  !selectedFile && fileInputRef.current?.click()
                }
                className={cn(
                  "relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-150",
                  isDragging
                    ? "border-[#7C3AED] bg-[#7C3AED]/5"
                    : selectedFile
                    ? "border-success/40 bg-success/5 cursor-default"
                    : "border-border hover:border-muted-foreground/40 cursor-pointer"
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf"
                  className="sr-only"
                  onChange={handleFileInput}
                />

                {selectedFile ? (
                  <div className="flex flex-col items-center gap-2">
                    <div className="h-10 w-10 rounded-full bg-success/10 flex items-center justify-center">
                      <FileText className="h-5 w-5 text-success" />
                    </div>
                    <p
                      className="text-sm font-medium text-foreground truncate max-w-[240px]"
                      title={selectedFile.name}
                    >
                      {selectedFile.name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {(selectedFile.size / 1024 / 1024).toFixed(1)} MB
                    </p>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedFile(null);
                      }}
                      className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-4"
                    >
                      Choose different file
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center">
                      <Upload className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <p className="text-sm font-medium text-foreground">
                      Drop a PDF here
                    </p>
                    <p className="text-xs text-muted-foreground">
                      or{" "}
                      <span className="text-[#7C3AED]">browse files</span>
                      {" · PDF · max 50 MB"}
                    </p>
                  </div>
                )}
              </div>

              <Button
                className="w-full bg-[#1F4E79] hover:bg-[#1F4E79]/90 text-white"
                onClick={handleUpload}
                disabled={!selectedFile || phase === "uploading"}
              >
                {phase === "uploading" ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Uploading…
                  </>
                ) : (
                  "Upload Document"
                )}
              </Button>
            </TabsContent>

            {/* EDGAR tab */}
            <TabsContent value="edgar" className="mt-4 space-y-4">
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="edgar-ticker" className="text-xs">
                    Ticker Symbol
                  </Label>
                  <Input
                    id="edgar-ticker"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value.toUpperCase())}
                    placeholder="AAPL"
                    maxLength={10}
                    className="font-mono uppercase tracking-wider"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs">Form Type</Label>
                    <Select
                      value={formType}
                      onValueChange={(v) => setFormType(v as FilingType)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {FILING_TYPES.map((t) => (
                          <SelectItem key={t} value={t}>
                            {t}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="edgar-year" className="text-xs">
                      Year
                    </Label>
                    <Input
                      id="edgar-year"
                      type="number"
                      value={year}
                      onChange={(e) => setYear(e.target.value)}
                      min={1993}
                      max={CURRENT_YEAR}
                      placeholder={String(CURRENT_YEAR - 1)}
                      className="font-mono"
                    />
                  </div>
                </div>

                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Fetches the filing directly from{" "}
                  <a
                    href="https://www.sec.gov/cgi-bin/browse-edgar"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#2E75B6] hover:underline underline-offset-4 inline-flex items-center gap-0.5"
                  >
                    SEC EDGAR
                    <ExternalLink className="h-2.5 w-2.5" />
                  </a>
                  . Large filings may take a moment to retrieve.
                </p>
              </div>

              <Button
                className="w-full bg-[#1F4E79] hover:bg-[#1F4E79]/90 text-white"
                onClick={handleEdgarFetch}
                disabled={phase === "uploading"}
              >
                {phase === "uploading" ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Fetching…
                  </>
                ) : (
                  "Fetch from EDGAR"
                )}
              </Button>
            </TabsContent>
          </Tabs>
        )}

        {/* ── Connecting to SSE (ingesting but no event yet) ── */}
        {phase === "ingesting" && !progress && (
          <div className="flex flex-col items-center gap-3 py-10">
            <Loader2 className="h-8 w-8 text-[#7C3AED] animate-spin" />
            <p className="text-sm text-muted-foreground">
              Connecting to ingestion stream…
            </p>
          </div>
        )}

        {/* ── Ingesting with progress ── */}
        {phase === "ingesting" && progress && (
          <IngestionProgress progress={progress} />
        )}

        {/* ── Done ── */}
        {phase === "done" && (
          <div className="flex flex-col items-center gap-3 py-10">
            <div className="h-14 w-14 rounded-full bg-success/10 flex items-center justify-center">
              <Check className="h-7 w-7 text-success" />
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-foreground">
                Document indexed successfully
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Closing in a moment…
              </p>
            </div>
          </div>
        )}

        {/* ── Error ── */}
        {phase === "error" && (
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="h-14 w-14 rounded-full bg-danger/10 flex items-center justify-center">
              <AlertCircle className="h-7 w-7 text-danger" />
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-foreground">
                Something went wrong
              </p>
              <p className="text-xs text-muted-foreground mt-1.5 max-w-[280px] leading-relaxed">
                {errorMessage}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={resetToIdle}>
              Try again
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ─── IngestionProgress display ────────────────────────────────────────────────

function IngestionProgress({ progress }: { progress: IngestionProgress }) {
  const currentStepIdx = PHASE_STEPS.findIndex(
    (s) => s.key === progress.phase
  );

  return (
    <div className="space-y-5 py-2">
      {/* Step indicators with connector lines */}
      <div className="flex items-start gap-0">
        {PHASE_STEPS.map((step, i) => {
          const isCompleted =
            progress.phase === "done"
              ? true
              : i < currentStepIdx;
          const isCurrent =
            progress.phase !== "done" && step.key === progress.phase;

          return (
            <div key={step.key} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-1">
                <div
                  className={cn(
                    "h-7 w-7 rounded-full flex items-center justify-center transition-all duration-300",
                    isCompleted
                      ? "bg-success text-white"
                      : isCurrent
                      ? "bg-[#7C3AED] text-white ring-2 ring-[#7C3AED]/30 ring-offset-2 ring-offset-card"
                      : "bg-muted text-muted-foreground/40"
                  )}
                >
                  {isCompleted ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : (
                    <span className="text-[10px] font-bold">{i + 1}</span>
                  )}
                </div>
                <span
                  className={cn(
                    "text-[9px] font-medium whitespace-nowrap",
                    isCompleted || isCurrent
                      ? "text-foreground"
                      : "text-muted-foreground/40"
                  )}
                >
                  {step.label}
                </span>
              </div>
              {/* Connector */}
              {i < PHASE_STEPS.length - 1 && (
                <div
                  className={cn(
                    "flex-1 h-px mx-1 mt-[-14px] transition-colors duration-500",
                    i < currentStepIdx || progress.phase === "done"
                      ? "bg-success"
                      : "bg-border"
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[12px] text-muted-foreground">
            {PHASE_LABELS[progress.phase] ?? progress.phase}
          </span>
          <span className="text-[12px] font-mono text-muted-foreground tabular-nums">
            {Math.round(progress.progress)}%
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-[#7C3AED] transition-all duration-500 ease-out"
            style={{ width: `${progress.progress}%` }}
          />
        </div>
      </div>

      {/* Status message */}
      {progress.message && (
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          {progress.message}
        </p>
      )}
    </div>
  );
}
