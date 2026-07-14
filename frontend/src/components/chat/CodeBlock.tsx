"use client";

import React, { useRef, useState } from "react";
import { Copy, Check } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface CodeBlockProps {
  children: React.ReactNode;
}

export function CodeBlock({ children }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const preRef = useRef<HTMLPreElement>(null);

  // Extract language from the code child's className (set by rehype-highlight)
  let language = "plaintext";
  React.Children.forEach(children, (child) => {
    if (React.isValidElement(child)) {
      const el = child as React.ReactElement<{ className?: string }>;
      const m = /language-(\w+)/.exec(el.props.className ?? "");
      if (m?.[1]) language = m[1];
    }
  });

  const handleCopy = async () => {
    const text = preRef.current?.innerText ?? "";
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success("Copied to clipboard", { duration: 2000 });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Could not access clipboard");
    }
  };

  return (
    <div className="group my-4 overflow-hidden rounded-lg border border-white/10 font-mono text-[13px]">
      {/* Header */}
      <div className="flex items-center justify-between bg-[#21252b] px-4 py-2 border-b border-white/10">
        <span className="text-[11px] text-neutral-500 uppercase tracking-wider">
          {language}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1.5 rounded px-2 py-1 text-[11px] text-neutral-400 hover:text-white hover:bg-white/10 transition-all duration-150"
          aria-label="Copy code to clipboard"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              Copy
            </>
          )}
        </button>
      </div>
      {/* Code body — atom-one-dark CSS handles background + text colors */}
      <pre
        ref={preRef}
        className="overflow-x-auto p-4 leading-relaxed !m-0 !rounded-none scrollbar-thin"
      >
        {children}
      </pre>
    </div>
  );
}
