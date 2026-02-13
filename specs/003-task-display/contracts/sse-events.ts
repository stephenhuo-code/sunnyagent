/**
 * SSE Event Contracts for Task Display Mode
 *
 * Feature: 003-task-display
 * Date: 2025-02-13
 *
 * This file defines the TypeScript interfaces for all SSE events.
 * It serves as the contract between backend and frontend.
 */

// =============================================================================
// Base Types
// =============================================================================

/**
 * Todo item from DeepAgents TodoListMiddleware
 */
export interface Todo {
  /** Task description */
  content: string;
  /** Current status */
  status: "pending" | "in_progress" | "completed";
}

// =============================================================================
// Existing Events (Backward Compatible)
// =============================================================================

/**
 * Streaming text content
 */
export interface TextDeltaEvent {
  event: "text_delta";
  data: {
    text: string;
  };
}

/**
 * Error occurred during processing
 */
export interface ErrorEvent {
  event: "error";
  data: {
    message: string;
  };
}

/**
 * Stream completed
 */
export interface DoneEvent {
  event: "done";
  data: Record<string, never>;
}

// =============================================================================
// Enhanced Events (Backward Compatible - new fields are optional)
// =============================================================================

/**
 * Agent thinking/reasoning step
 *
 * Enhanced: Added optional `type` field to distinguish planning phases
 */
export interface ThinkingEvent {
  event: "thinking";
  data: {
    /** Type of thinking (optional for backward compatibility) */
    type?: "planning" | "replanning" | "routing";
    /** Thinking content */
    content: string;
  };
}

/**
 * Tool call started
 *
 * Enhanced: Added optional `task_id` to associate with parent task
 */
export interface ToolCallStartEvent {
  event: "tool_call_start";
  data: {
    /** Unique tool call ID */
    id: string;
    /** Parent task ID (optional for backward compatibility) */
    task_id?: string;
    /** Tool name */
    name: string;
    /** Tool arguments */
    args: Record<string, unknown>;
  };
}

/**
 * Tool call completed
 *
 * Enhanced: Added optional `task_id` to associate with parent task
 */
export interface ToolCallResultEvent {
  event: "tool_call_result";
  data: {
    /** Tool call ID (matches tool_call_start) */
    id: string;
    /** Parent task ID (optional for backward compatibility) */
    task_id?: string;
    /** Tool name */
    name: string;
    /** Execution status */
    status: "success" | "error";
    /** Tool output (truncated to 2000 chars) */
    output: string;
  };
}

// =============================================================================
// New Events
// =============================================================================

/**
 * Todo list updated (planning/replanning/status change)
 *
 * Triggered when TodoListMiddleware state changes
 */
export interface TodosUpdatedEvent {
  event: "todos_updated";
  data: {
    /** Complete todo list (full state, not delta) */
    todos: Todo[];
    /** ISO 8601 timestamp */
    timestamp: string;
  };
}

/**
 * Sub-agent task spawned
 *
 * Triggered when SubAgentMiddleware task() tool is called
 */
export interface TaskSpawnedEvent {
  event: "task_spawned";
  data: {
    /** Unique task ID */
    task_id: string;
    /** Agent type (sql, research, etc.) */
    subagent_type: string;
    /** Task description */
    description: string;
  };
}

/**
 * Sub-agent task completed
 *
 * Triggered when SubAgentMiddleware task() tool returns
 */
export interface TaskCompletedEvent {
  event: "task_completed";
  data: {
    /** Task ID (matches task_spawned) */
    task_id: string;
    /** Execution duration in milliseconds */
    duration_ms: number;
    /** Final status */
    status: "success" | "error";
  };
}

// =============================================================================
// Union Type
// =============================================================================

/**
 * All possible SSE events
 */
export type SSEEvent =
  | TextDeltaEvent
  | ErrorEvent
  | DoneEvent
  | ThinkingEvent
  | ToolCallStartEvent
  | ToolCallResultEvent
  | TodosUpdatedEvent
  | TaskSpawnedEvent
  | TaskCompletedEvent;

// =============================================================================
// Type Guards
// =============================================================================

export function isTextDeltaEvent(event: SSEEvent): event is TextDeltaEvent {
  return event.event === "text_delta";
}

export function isThinkingEvent(event: SSEEvent): event is ThinkingEvent {
  return event.event === "thinking";
}

export function isToolCallStartEvent(event: SSEEvent): event is ToolCallStartEvent {
  return event.event === "tool_call_start";
}

export function isToolCallResultEvent(event: SSEEvent): event is ToolCallResultEvent {
  return event.event === "tool_call_result";
}

export function isTodosUpdatedEvent(event: SSEEvent): event is TodosUpdatedEvent {
  return event.event === "todos_updated";
}

export function isTaskSpawnedEvent(event: SSEEvent): event is TaskSpawnedEvent {
  return event.event === "task_spawned";
}

export function isTaskCompletedEvent(event: SSEEvent): event is TaskCompletedEvent {
  return event.event === "task_completed";
}

export function isErrorEvent(event: SSEEvent): event is ErrorEvent {
  return event.event === "error";
}

export function isDoneEvent(event: SSEEvent): event is DoneEvent {
  return event.event === "done";
}
