import Image from "next/image";
import { Zap, GitMerge, BarChart3 } from "lucide-react";

const FEATURES = [
  {
    icon: Zap,
    label: "Vectorless RAG — tree navigation, no embeddings needed",
    sub: "2× faster than traditional vector search",
  },
  {
    icon: GitMerge,
    label: "Hybrid fallback for cross-document comparisons",
    sub: "Dense + BM25 fusion with cross-encoder reranking",
  },
  {
    icon: BarChart3,
    label: "80%+ accuracy on custom financial benchmark",
    sub: "Tesla · NVIDIA · Apple · Microsoft 10-K filings",
  },
] as const;

export function AuthPanel() {
  return (
    // hidden on mobile (< lg) — form takes full width instead
    // On tablet (lg) it flexes in beside the form panel
    <div className="hidden lg:flex lg:flex-1 relative overflow-hidden select-none">

      {/* Gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-[#0f2744] via-[#1F4E79] to-[#5b21b6]" />

      {/* Subtle grid overlay */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px),
                            linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)`,
          backgroundSize: "40px 40px",
        }}
      />

      {/* Ambient orbs */}
      <div className="absolute top-1/4 -left-16 h-80 w-80 rounded-full bg-[#7C3AED]/20 blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-0 h-64 w-64 rounded-full bg-[#2E75B6]/25 blur-2xl pointer-events-none" />
      <div className="absolute top-2/3 left-1/4 h-40 w-40 rounded-full bg-white/5 blur-2xl pointer-events-none" />

      {/* Content */}
      {/* px/py slightly tighter on lg, relaxes on xl */}
      <div className="relative z-10 flex flex-col justify-between w-full
                      px-10 py-10
                      xl:px-14 xl:py-14">

        {/* Top — logo wordmark */}
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/20">
            <Image src="/logo.svg" alt="" width={20} height={20} />
          </div>
          <span className="text-sm xl:text-base font-semibold text-white tracking-tight">
            FinDoc Intelligence
          </span>
        </div>

        {/* Middle — quote */}
        <div className="space-y-6 my-auto py-10 xl:py-12">
          {/* Decorative quote mark */}
          <div className="text-5xl xl:text-6xl font-serif text-white/10 leading-none select-none">
            &ldquo;
          </div>
          <blockquote className="space-y-4 -mt-4">
            <p className="text-[1.1rem] xl:text-[1.3rem] font-light text-white/90
                          leading-[1.7] max-w-[300px] xl:max-w-[340px]">
              Vectorless RAG navigates financial documents the way a senior
              analyst does — by following structure, not hunting keywords.
            </p>
            <footer className="flex items-center gap-2">
              <div className="h-px w-6 bg-white/30" />
              <span className="text-[11px] text-white/40 font-mono tracking-wide">
                PageIndex · VectifyAI
              </span>
            </footer>
          </blockquote>
        </div>

        {/* Bottom — feature cards */}
        {/* gap and padding slightly tighter on lg, more spacious on xl */}
        <ul className="flex flex-col gap-2 xl:gap-2.5" aria-label="Key features">
          {FEATURES.map(({ icon: Icon, label, sub }) => (
            <li
              key={label}
              className="flex items-start gap-3 xl:gap-3.5 rounded-xl
                         bg-white/6 border border-white/10
                         px-3 py-3 xl:px-4 xl:py-3.5
                         backdrop-blur-sm hover:bg-white/10 transition-colors duration-150"
            >
              <div className="flex h-7 w-7 shrink-0 items-center justify-center
                              rounded-lg bg-white/10 mt-0.5">
                <Icon className="h-3.5 w-3.5 text-white/70" aria-hidden />
              </div>
              <div className="min-w-0">
                <p className="text-[12px] xl:text-[13px] font-medium text-white/85 leading-snug">
                  {label}
                </p>
                <p className="text-[11px] text-white/40 mt-0.5 leading-snug">
                  {sub}
                </p>
              </div>
            </li>
          ))}
        </ul>

      </div>
    </div>
  );
}