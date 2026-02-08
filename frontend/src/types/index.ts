/** A registered agent */
export interface Agent {
  name: string;
  description: string;
  icon: string;
}

/** A registered skill */
export interface Skill {
  name: string;
  description: string;
}

/** SSE event types from the backend */
export type SSEEvent =
  | { event: "text_delta"; data: { text: string } }
  | {
      event: "tool_call_start";
      data: { id: string; name: string; args: Record<string, unknown> };
    }
  | {
      event: "tool_call_result";
      data: { id: string; name: string; status: string; output: string };
    }
  | { event: "thinking"; data: { content: string } }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: Record<string, never> };

/** A tool call with its current status */
export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  status: "running" | "done" | "error";
  output?: string;
}

/** Thinking bubble state for agent reasoning steps */
export interface ThinkingState {
  steps: string[];
  isThinking: boolean;
  startTime: number;
  durationSeconds: number;
}

/** File attachment in a message */
export interface FileAttachment {
  file_id: string;
  filename: string;
  size: number;
  content_type: string;
  source: "user" | "agent";
  download_url: string;
}

/** Uploaded file info returned from server */
export interface UploadedFile {
  file_id: string;
  filename: string;
  size: number;
  content_type: string;
  download_url: string;
}

/** File being uploaded with progress */
export interface UploadingFile {
  id: string;
  file: File;
  progress: number;
  status: "uploading" | "completed" | "error";
  uploadedFile?: UploadedFile;
  error?: string;
}

/** A single chat message */
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCall[];
  thinking?: ThinkingState;
  files?: FileAttachment[];
}
