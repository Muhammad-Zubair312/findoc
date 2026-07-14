"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/lib/api/findoc";
import { useChatStore } from "@/lib/stores/chatStore";

export function useFeedback() {
  const updateMessage = useChatStore((s) => s.updateMessage);
  const activeConversationId = useChatStore((s) => s.activeConversationId);

  return useMutation({
    mutationFn: ({
      message_id,
      feedback,
    }: {
      message_id: string;
      feedback: "up" | "down";
    }) => api.submitFeedback(message_id, feedback),
    onMutate: ({ message_id, feedback }) => {
      if (!activeConversationId) return;
      updateMessage(activeConversationId, message_id, { feedback });
    },
    onError: (e: Error, { message_id }) => {
      if (!activeConversationId) return;
      updateMessage(activeConversationId, message_id, { feedback: null });
      toast.error("Could not save feedback: " + e.message);
    },
  });
}
