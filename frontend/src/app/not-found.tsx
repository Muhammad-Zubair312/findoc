import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background gap-6 p-6 text-center">
      {/* Numeric */}
      <div className="relative">
        <span className="text-[120px] font-black text-muted/20 leading-none select-none">
          404
        </span>
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="h-16 w-16 rounded-2xl bg-[#1F4E79]/10 flex items-center justify-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#1F4E79"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="9" y1="15" x2="15" y2="15" />
            </svg>
          </div>
        </div>
      </div>

      <div className="space-y-2 max-w-[340px]">
        <h1 className="text-xl font-semibold text-foreground">
          Page not found
        </h1>
        <p className="text-sm text-muted-foreground leading-relaxed">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <Link
          href="/chat"
          className="inline-flex items-center gap-2 rounded-lg bg-[#1F4E79] px-4 py-2 text-sm font-medium text-white hover:bg-[#1F4E79]/90 transition-colors"
        >
          Go to Chat
        </Link>
        <Link
          href="/documents"
          className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
        >
          Documents
        </Link>
      </div>
    </div>
  );
}
