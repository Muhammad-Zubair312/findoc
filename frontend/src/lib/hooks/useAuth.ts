"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import api from "@/lib/api/findoc";
import type { User } from "@/lib/types";

export function useAuth() {
  const queryClient = useQueryClient();
  const router = useRouter();

  const {
    data: user,
    isLoading,
    error,
  } = useQuery<User | null>({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      try {
        return await api.getMe();
      } catch (e: unknown) {
        const err = e as Error & { status?: number };
        if (err.status === 401) return null;
        throw e;
      }
    },
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const loginMutation = useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.login(email, password),
    onSuccess: (data) => {
      queryClient.setQueryData(["auth", "me"], data.user);
      router.push("/chat");
    },
    onError: (e: Error) => {
      toast.error(e.message || "Login failed. Check your credentials.");
    },
  });

  const registerMutation = useMutation({
    mutationFn: ({
      email,
      password,
      full_name,
    }: {
      email: string;
      password: string;
      full_name: string;
    }) => api.register(email, password, full_name),
    onSuccess: (data) => {
      queryClient.setQueryData(["auth", "me"], data.user);
      router.push("/chat");
    },
    onError: (e: Error) => {
      toast.error(e.message || "Registration failed. Please try again.");
    },
  });

  const logoutMutation = useMutation({
    mutationFn: () => api.logout(),
    onSettled: () => {
      queryClient.clear();
      router.push("/login");
    },
  });

  return {
    user: user ?? null,
    isLoading,
    isAuthenticated: !!user,
    error,
    login: loginMutation.mutate,
    isLoginPending: loginMutation.isPending,
    register: registerMutation.mutate,
    isRegisterPending: registerMutation.isPending,
    logout: logoutMutation.mutate,
  };
}
