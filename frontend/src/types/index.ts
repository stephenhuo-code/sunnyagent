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
  source?: string;
  skill_type?: "atomic" | "workflow";
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
  status: "pending" | "running" | "success" | "error" | "failed" | "cancelled";
  duration_ms?: number;
  toolCalls: ToolCall[];
  output?: string;  // Task output content (collected from task_output events)
  todos?: Todo[];   // Agent internal todos associated with this task
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
  | { event: "todos_updated"; data: { todos: Todo[]; timestamp: string; task_id?: string } }
  | { event: "task_spawned"; data: { task_id: string; subagent_type: string; description: string; status?: "pending" | "running" } }
  | { event: "task_started"; data: { task_id: string } }
  | { event: "task_completed"; data: { task_id: string; duration_ms?: number; status: "success" | "error" | "failed" | "cancelled" } }
  | { event: "task_output"; data: { task_id: string; text: string } };

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
  steps: ThinkingStep[];     // Thinking steps from backend thinking events
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

// =============================================================================
// Project Management Types
// =============================================================================

/** Project summary for list display */
export interface Project {
  id: string;
  name: string;
  file_count: number;
  conversation_count: number;
  created_at: string;
  updated_at: string;
}

/** File in a project */
export interface ProjectFile {
  id: string;
  file_id: string;
  original_name: string;
  content_type: string | null;
  size_bytes: number;
  created_at: string;
  download_url: string;
  /** UI state: selected for chat context */
  selected?: boolean;
}

/** Uploading file state */
export interface UploadingProjectFile {
  id: string;
  file: File;
  progress: number;
  status: "uploading" | "completed" | "error";
  projectFile?: ProjectFile;
  error?: string;
}
