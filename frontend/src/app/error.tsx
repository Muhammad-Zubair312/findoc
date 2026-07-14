"use client";

import { useEffect } from "react";
import Link from "next/link";

interface ErrorPageProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    console.error("[GlobalError]", error);
  }, [error]);

  return (
    <html lang="en">
      <body className="min-h-screen bg-[#0f1117] flex flex-col items-center justify-center gap-6 p-6 text-center font-sans">
        <div className="h-14 w-14 rounded-full bg-red-500/10 flex items-center justify-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#EF4444"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>

        <div className="space-y-2 max-w-[340px]">
          <h1 className="text-xl font-semibold text-white">
            Something went wrong
          </h1>
          <p className="text-sm text-gray-400 leading-relaxed">
            An unexpected error occurred. Our team has been notified.
          </p>
          {error.digest && (
            <p className="text-[11px] font-mono text-gray-600 mt-1">
              Error ID: {error.digest}
            </p>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={reset}
            className="inline-flex items-center gap-2 rounded-lg bg-[#1F4E79] px-4 py-2 text-sm font-medium text-white hover:bg-[#1F4E79]/90 transition-colors"
          >
            Try again
          </button>
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-800 transition-colors"
          >
            Go home
          </Link>
        </div>
      </body>
    </html>
  );
}
