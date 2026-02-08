import type { Agent, Skill, SSEEvent, UploadedFile } from "../types";

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
  skill?: string,
  fileIds?: string[],
): AsyncGenerator<SSEEvent> {
  const body: Record<string, unknown> = { thread_id: threadId, message };
  if (agent) body.agent = agent;
  if (skill) body.skill = skill;
  if (fileIds && fileIds.length > 0) body.file_ids = fileIds;

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
          console.log(`[SSE_EVENT] event=${currentEvent}, data=`, data);
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

/** Fetch all registered skills. */
export async function getSkills(): Promise<Skill[]> {
  const response = await fetch("/api/skills");
  return response.json();
}

/** Upload a file with progress tracking. */
export function uploadFile(
  file: File,
  onProgress?: (progress: number) => void
): Promise<UploadedFile> {
  const formData = new FormData();
  formData.append("file", file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status === 200) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        try {
          const error = JSON.parse(xhr.responseText);
          reject(new Error(error.detail || "Upload failed"));
        } catch {
          reject(new Error("Upload failed"));
        }
      }
    };

    xhr.onerror = () => {
      reject(new Error("Network error"));
    };

    xhr.open("POST", "/api/files/upload");
    xhr.send(formData);
  });
}

/** Fetch file content for preview. */
export async function getFileContent(fileId: string): Promise<{ content: string; filename: string }> {
  const response = await fetch(`/api/files/${fileId}/content`);
  if (!response.ok) {
    throw new Error("Failed to load file content");
  }
  return response.json();
}
