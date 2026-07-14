"use client";

import {
  useRef,
  useEffect,
  useCallback,
  KeyboardEvent,
  useState,
} from "react";
import { ArrowUp, Paperclip, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DocumentSelector } from "@/components/chat/DocumentSelector";
import { useChatStore } from "@/lib/stores/chatStore";
import { cn } from "@/lib/utils";
import api from "@/lib/api/findoc";
import { toast } from "sonner";

interface ChatInputProps {
  onSend: (query: string, documentIds: string[]) => void;
  disabled?: boolean;
  placeholder?: string;
  initialValue?: string;
  onInitialValueConsumed?: () => void;
}

async function pollUntilReady(documentId: string): Promise<boolean> {
  const MAX_POLLS = 120;
  const INTERVAL_MS = 5000;
  for (let i = 0; i < MAX_POLLS; i++) {
    await new Promise((r) => setTimeout(r, INTERVAL_MS));
    try {
      const doc = await api.getDocument(documentId);
      if (doc.status === "indexed") return true;
      if (doc.status === "failed") return false;
    } catch {
      // transient — keep polling
    }
  }
  return false;
}

const UPLOAD_STAGES = [
  "Parsing SEC filing structure...",
  "Building section tree...",
  "Generating section summaries...",
  "Creating embeddings...",
  "Finalizing document index...",
];

export function ChatInput({
  onSend,
  disabled,
  placeholder = "Ask about a filing...",
  initialValue,
  onInitialValueConsumed,
}: ChatInputProps) {
  const [value, setValue] = useState(initialValue ?? "");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStage, setUploadStage] = useState("");
  const [uploadFileName, setUploadFileName] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { selectedDocumentIds } = useChatStore();

  useEffect(() => {
    if (initialValue !== undefined && initialValue !== value) {
      setValue(initialValue);
      adjustHeight();
      textareaRef.current?.focus();
      onInitialValueConsumed?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialValue]);

  useEffect(() => {
    const handleKey = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "/") {
        e.preventDefault();
        textareaRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  const adjustHeight = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    const maxH = 22 * 8 + 24;
    ta.style.height = Math.min(ta.scrollHeight, maxH) + "px";
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled || isUploading) return;
    onSend(trimmed, selectedDocumentIds);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, disabled, isUploading, onSend, selectedDocumentIds]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSend();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleAttachClick = () => {
    if (disabled || isUploading) return;
    fileInputRef.current?.click();
  };

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      e.target.value = "";

      const ext = "." + (file.name.split(".").pop()?.toLowerCase() ?? "");
      if (![".htm", ".html", ".pdf"].includes(ext)) {
        toast.error(
          `Unsupported file: ${ext}. Please upload an SEC filing (.htm, .html, or .pdf).`
        );
        return;
      }
      if (file.size > 50 * 1024 * 1024) {
        toast.error("File too large. Maximum 50MB.");
        return;
      }

      setIsUploading(true);
      setUploadFileName(file.name);
      setUploadStage(UPLOAD_STAGES[0]);

      let stageIdx = 0;
      const stageTimer = setInterval(() => {
        stageIdx = Math.min(stageIdx + 1, UPLOAD_STAGES.length - 1);
        setUploadStage(UPLOAD_STAGES[stageIdx]);
      }, 30000);

      try {
        const { document_id } = await api.uploadDocument(file);
        stageIdx = 1;
        setUploadStage(UPLOAD_STAGES[1]);

        const success = await pollUntilReady(document_id);
        clearInterval(stageTimer);

        if (success) {
          toast.success(
            `${file.name} indexed successfully! You can now ask questions about it.`,
            { duration: 6000 }
          );
        } else {
          toast.error(`Failed to index ${file.name}. Please try again.`, {
            duration: 8000,
          });
        }
      } catch (err) {
        clearInterval(stageTimer);
        toast.error(
          `Upload failed: ${err instanceof Error ? err.message : "Unknown error"}`,
          { duration: 8000 }
        );
      } finally {
        setIsUploading(false);
        setUploadStage("");
        setUploadFileName("");
      }
    },
    []
  );

  const canSend = value.trim().length > 0 && !disabled && !isUploading;

  return (
    <>
      {/* ── Full-screen upload overlay ─────────────────────────────────────── */}
      {isUploading && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
          aria-live="polite"
          aria-label="Document uploading, please wait"
        >
          <div className="flex flex-col items-center gap-5 rounded-2xl border border-[#7C3AED]/20 bg-card px-8 py-7 shadow-2xl w-full max-w-sm mx-4">
            <div className="relative flex h-16 w-16 items-center justify-center">
              <div className="absolute inset-0 rounded-full border-4 border-[#7C3AED]/10" />
              <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-[#7C3AED] animate-spin" />
              <Paperclip className="h-6 w-6 text-[#7C3AED]" />
            </div>
            <div className="text-center space-y-1">
              <p className="text-sm font-semibold text-foreground">
                Indexing Document
              </p>
              <p className="text-xs text-muted-foreground max-w-[240px] truncate">
                {uploadFileName}
              </p>
            </div>
            <div className="w-full rounded-lg bg-muted/50 px-4 py-2.5 text-center">
              <p className="text-xs font-medium text-[#7C3AED]">{uploadStage}</p>
            </div>
            <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
              <div className="h-full w-full rounded-full bg-[#7C3AED] animate-pulse opacity-60" />
            </div>
            <p className="text-[11px] text-muted-foreground text-center leading-relaxed">
              SEC filings take 5–15 minutes to index.
              <br />
              Please keep this tab open.
            </p>
          </div>
        </div>
      )}

      {/* ── Input area ─────────────────────────────────────────────────────── */}
      {/* Tighter horizontal padding on mobile, relaxes on sm+ */}
      <div className="px-3 pb-3 pt-2 sm:px-4 sm:pb-4">
        <input
          ref={fileInputRef}
          type="file"
          accept=".htm,.html,.pdf"
          className="hidden"
          onChange={handleFileChange}
          aria-hidden="true"
        />

        {/* Unified input box */}
        <div
          className={cn(
            "relative overflow-hidden rounded-2xl border bg-card shadow-sm",
            "transition-all duration-200",
            "border-input hover:border-[#7C3AED]/30",
            "focus-within:border-[#7C3AED]/60",
            "focus-within:shadow-[0_0_0_3px_rgba(124,58,237,0.10)]",
            disabled && "opacity-60 pointer-events-none"
          )}
        >
          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              adjustHeight();
            }}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={placeholder}
            rows={1}
            aria-label="Message input"
            className={cn(
              "block w-full resize-none bg-transparent",
              "px-3 pt-3 pb-1 sm:px-4 sm:pt-3.5",
              "text-sm text-foreground placeholder:text-muted-foreground",
              "outline-none ring-0 border-0",
              "focus:outline-none focus:ring-0 focus:border-0",
              "leading-relaxed scrollbar-thin disabled:cursor-not-allowed"
            )}
            style={{
              minHeight: "50px",
              maxHeight: `${22 * 8 + 24}px`,
              boxShadow: "none",
            }}
          />

          {/* Toolbar row */}
          <div className="flex items-center gap-1 px-2 pb-2 pt-1 sm:gap-1.5 sm:px-3 sm:pb-2.5">
            <DocumentSelector />

            {/* Attach button — larger tap area on mobile */}
            <button
              type="button"
              onClick={handleAttachClick}
              disabled={disabled || isUploading}
              title="Upload SEC filing (.htm, .html, .pdf)"
              aria-label="Upload SEC filing"
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-lg transition-colors touch-manipulation",
                "text-muted-foreground hover:text-foreground hover:bg-accent",
                "disabled:pointer-events-none disabled:opacity-40"
              )}
            >
              {isUploading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-[#7C3AED]" />
              ) : (
                <Paperclip className="h-3.5 w-3.5" />
              )}
            </button>

            {value.length > 500 && (
              <span
                className={cn(
                  "ml-1 text-[11px] font-mono tabular-nums",
                  value.length > 2000
                    ? "text-destructive"
                    : "text-muted-foreground"
                )}
                aria-live="polite"
              >
                {value.length.toLocaleString()}
              </span>
            )}

            {/* Send button */}
            <Button
              type="button"
              size="icon"
              onClick={handleSend}
              disabled={!canSend}
              aria-label="Send message"
              className={cn(
                "ml-auto h-8 w-8 rounded-xl shrink-0 transition-all duration-150 touch-manipulation",
                canSend
                  ? "bg-[#7C3AED] hover:bg-[#6d33d4] text-white shadow-sm hover:scale-105 active:scale-95"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              )}
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Hint text — hidden on mobile to save space, visible sm+ */}
        <p className="hidden sm:block mt-1.5 text-[11px] text-muted-foreground/50 text-center">
          Enter to send · Shift+Enter for newline · Cmd+/ to focus
        </p>
      </div>
    </>
  );
}