"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/lib/api/findoc";

export function useEvalSummary() {
  return useQuery({
    queryKey: ["eval", "summary"],
    queryFn: () => api.getEvalSummary(),
    staleTime: 60 * 1000,
    retry: 1,
  });
}

export function useEvalHistory(days = 30) {
  return useQuery({
    queryKey: ["eval", "history", days],
    queryFn: () => api.getEvalHistory(days),
    staleTime: 60 * 1000,
    retry: 1,
  });
}

export function useEvalFailures(limit = 10) {
  return useQuery({
    queryKey: ["eval", "failures", limit],
    queryFn: () => api.getEvalFailures(limit),
    staleTime: 60 * 1000,
    retry: 1,
  });
}

export function useRunEval() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.runEval(),
    onSuccess: () => {
      toast.success("Benchmark started. Results will appear when complete.");
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["eval"] });
      }, 5000);
    },
    onError: (e: Error) => toast.error(e.message),
  });
}
