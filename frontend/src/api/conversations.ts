/**
 * API client for conversation management
 */

import { handleUnauthorized } from '../hooks/useAuth';

function checkUnauthorized(res: Response) {
  if (res.status === 401) {
    handleUnauthorized();
  }
}

export interface ConversationSummary {
  id: string;
  title: string;
  project_id: string | null;
  updated_at: string;
}

export interface Conversation {
  id: string;
  thread_id: string;
  title: string;
  project_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  conversations: ConversationSummary[];
  total: number;
}

/**
 * List conversations for the current user
 */
export async function listConversations(
  limit: number = 50,
  offset: number = 0,
  options?: { projectId?: string; excludeProject?: boolean }
): Promise<ConversationListResponse> {
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });

  if (options?.projectId) {
    params.set('project_id', options.projectId);
  }
  if (options?.excludeProject) {
    params.set('exclude_project', 'true');
  }

  const res = await fetch(`/api/conversations?${params}`, {
    credentials: "include",
  });
  checkUnauthorized(res);
  if (!res.ok) {
    throw new Error("Failed to list conversations");
  }
  return res.json();
}

export interface CreateConversationOptions {
  title?: string;
  project_id?: string;
}

/**
 * Create a new conversation
 */
export async function createConversation(
  options?: string | CreateConversationOptions
): Promise<Conversation> {
  // Support both old signature (title only) and new signature (options object)
  const body: { title: string; project_id?: string } = {
    title: "New Conversation",
  };

  if (typeof options === "string") {
    body.title = options;
  } else if (options) {
    if (options.title) body.title = options.title;
    if (options.project_id) body.project_id = options.project_id;
  }

  const res = await fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error("Failed to create conversation");
  }
  return res.json();
}

/**
 * Get a conversation by ID
 */
export async function getConversation(id: string): Promise<Conversation> {
  const res = await fetch(`/api/conversations/${id}`, {
    credentials: "include",
  });
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error("Conversation not found");
    }
    throw new Error("Failed to get conversation");
  }
  return res.json();
}

/**
 * Update a conversation's title
 */
export async function updateConversation(
  id: string,
  title: string
): Promise<Conversation> {
  const res = await fetch(`/api/conversations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ title }),
  });
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error("Conversation not found");
    }
    throw new Error("Failed to update conversation");
  }
  return res.json();
}

/**
 * Delete a conversation
 */
export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(`/api/conversations/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error("Conversation not found");
    }
    throw new Error("Failed to delete conversation");
  }
}
