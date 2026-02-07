import type { Agent, SSEEvent } from "../types";

/**
 * Stream chat responses from the backend via SSE.
 *
 * Uses fetch + ReadableStream instead of EventSource because we need
 * to send a POST body with the message.
 */
export async function* streamChat(
  threadId: string,
  message: string,
  signal: AbortSignal,
  agent?: string,
): AsyncGenerator<SSEEvent> {
  const body: Record<string, string> = { thread_id: threadId, message };
  if (agent) body.agent = agent;

  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    // Keep the last (potentially incomplete) line in the buffer
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ") && currentEvent) {
        try {
          const data = JSON.parse(line.slice(6));
          yield { event: currentEvent, data } as SSEEvent;
        } catch {
          // Skip malformed JSON
        }
        currentEvent = "";
      }
      // Skip empty lines and comments (: keepalive)
    }
  }
}

/** Create a new thread and return its ID. */
export async function createThread(): Promise<string> {
  const response = await fetch("/api/threads", { method: "POST" });
  const data = await response.json();
  return data.thread_id;
}

/** Fetch all registered agents. */
export async function getAgents(): Promise<Agent[]> {
  const response = await fetch("/api/agents");
  return response.json();
}
