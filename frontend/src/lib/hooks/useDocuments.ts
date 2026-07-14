"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/lib/api/findoc";
import type { FilingType } from "@/lib/types";

export function useDocuments(params?: {
  filing_type?: FilingType | "all";
  sort?: "date_desc" | "date_asc" | "name";
  search?: string;
}) {
  return useQuery({
    queryKey: ["documents", params],
    queryFn: () => api.listDocuments(params),
    staleTime: 30 * 1000,
  });
}

export function useDocument(id: string) {
  return useQuery({
    queryKey: ["documents", id],
    queryFn: () => api.getDocument(id),
    enabled: !!id,
    staleTime: 30 * 1000,
  });
}

export function useDocumentTree(id: string) {
  return useQuery({
    queryKey: ["documents", id, "tree"],
    queryFn: () => api.getDocumentTree(id),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteDocument(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast.success("Document deleted.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useReingestDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.reingestDocument(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast.success("Re-ingestion started.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useLoadSample() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.loadSampleDocument(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast.success("Tesla 10-K loaded successfully.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}
