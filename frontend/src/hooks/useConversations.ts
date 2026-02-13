/**
 * Hook for managing conversation list state
 */

import { useState, useEffect, useCallback } from "react";
import {
  listConversations,
  createConversation,
  updateConversation,
  deleteConversation,
  type ConversationSummary,
  type Conversation,
} from "../api/conversations";

export interface UseConversationsResult {
  conversations: ConversationSummary[];
  total: number;
  isLoading: boolean;
  error: string | null;
  selectedId: string | null;
  refresh: () => Promise<void>;
  create: (title?: string) => Promise<Conversation>;
  update: (id: string, title: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
  select: (id: string | null) => void;
  clearSelection: () => void;
}

const STORAGE_KEY = "selected-conversation-id";

export function useConversations(): UseConversationsResult {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem(STORAGE_KEY);
    }
    return null;
  });

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await listConversations();
      setConversations(result.conversations);
      setTotal(result.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load conversations");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const create = useCallback(async (title?: string): Promise<Conversation> => {
    const conversation = await createConversation(title);
    // Add to beginning of list
    setConversations((prev) => [
      {
        id: conversation.id,
        title: conversation.title,
        updated_at: conversation.updated_at,
      },
      ...prev,
    ]);
    setTotal((prev) => prev + 1);
    setSelectedId(conversation.id);
    localStorage.setItem(STORAGE_KEY, conversation.id);
    return conversation;
  }, []);

  const update = useCallback(async (id: string, title: string) => {
    await updateConversation(id, title);
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title } : c))
    );
  }, []);

  const remove = useCallback(async (id: string) => {
    await deleteConversation(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    setTotal((prev) => prev - 1);
    if (selectedId === id) {
      setSelectedId(null);
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [selectedId]);

  const select = useCallback((id: string | null) => {
    setSelectedId(id);
    if (id) {
      localStorage.setItem(STORAGE_KEY, id);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedId(null);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  // Load conversations on mount
  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    conversations,
    total,
    isLoading,
    error,
    selectedId,
    refresh,
    create,
    update,
    remove,
    select,
    clearSelection,
  };
}
