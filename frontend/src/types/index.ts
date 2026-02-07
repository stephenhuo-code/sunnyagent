/** A registered agent */
export interface Agent {
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

/** A single chat message */
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCall[];
}
