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

/** Todo item from DeepAgents TodoListMiddleware */
export interface Todo {
  content: string;
  status: "pending" | "in_progress" | "completed";
}

/** Sub-agent task spawned via SubAgentMiddleware */
export interface SpawnedTask {
  task_id: string;
  subagent_type: string;
  description: string;
  status: "running" | "success" | "error";
  duration_ms?: number;
  toolCalls: ToolCall[];
}

/** Individual thinking step with type categorization */
export interface ThinkingStep {
  type?: "planning" | "replanning" | "routing";
  content: string;
  timestamp: number;
}

/** Display scenario type for three-layer structure */
export type DisplayScenario = "quick" | "agent" | "planning";

/** SSE event types from the backend */
export type SSEEvent =
  | { event: "text_delta"; data: { text: string } }
  | {
      event: "tool_call_start";
      data: { id: string; task_id?: string; name: string; args: Record<string, unknown> };
    }
  | {
      event: "tool_call_result";
      data: { id: string; task_id?: string; name: string; status: string; output: string };
    }
  | { event: "thinking"; data: { type?: "planning" | "replanning" | "routing"; content: string } }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: Record<string, never> }
  | { event: "todos_updated"; data: { todos: Todo[]; timestamp: string } }
  | { event: "task_spawned"; data: { task_id: string; subagent_type: string; description: string } }
  | { event: "task_completed"; data: { task_id: string; duration_ms: number; status: "success" | "error" } };

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
  steps: string[];           // Thinking steps from backend thinking events
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
  /** Display scenario for three-layer structure */
  displayScenario?: DisplayScenario;
  /** Todo list from autonomous planning mode */
  todos?: Todo[];
  /** Spawned sub-agent tasks */
  spawnedTasks?: SpawnedTask[];
}
