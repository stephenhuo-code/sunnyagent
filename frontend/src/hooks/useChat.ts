import { useCallback, useRef, useState } from "react";
import { createThread, streamChat } from "../api/client";
import type { Agent, Message, ToolCall } from "../types";

/** Parse /command prefix: "/research AI news" → { agent: "research", message: "AI news" } */
function parseSlashCommand(
  text: string,
  agents: Agent[],
): { agent?: string; message: string } {
  const match = text.match(/^\/(\S+)\s+([\s\S]+)/);
  if (match) {
    const name = match[1];
    if (agents.some((a) => a.name === name)) {
      return { agent: name, message: match[2] };
    }
  }
  return { message: text };
}

let msgCounter = 0;
function nextId() {
  return `msg-${++msgCounter}`;
}

export function useChat(agents: Agent[]) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (text: string) => {
      if (isStreaming || !text.trim()) return;

      // Parse /command prefix
      const { agent, message: actualMessage } = parseSlashCommand(
        text.trim(),
        agents,
      );

      // Create thread on first message
      let currentThreadId = threadId;
      if (!currentThreadId) {
        currentThreadId = await createThread();
        setThreadId(currentThreadId);
      }

      // Add user message
      const userMsg: Message = { id: nextId(), role: "user", content: text };
      setMessages((prev) => [...prev, userMsg]);

      // Prepare assistant message placeholder
      const assistantId = nextId();
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        toolCalls: [],
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        for await (const event of streamChat(
          currentThreadId,
          actualMessage,
          controller.signal,
          agent,
        )) {
          switch (event.event) {
            case "text_delta":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + event.data.text }
                    : m,
                ),
              );
              break;

            case "tool_call_start": {
              const tc: ToolCall = {
                id: event.data.id,
                name: event.data.name,
                args: event.data.args,
                status: "running",
              };
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, toolCalls: [...(m.toolCalls ?? []), tc] }
                    : m,
                ),
              );
              break;
            }

            case "tool_call_result":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: (m.toolCalls ?? []).map((tc) =>
                          tc.id === event.data.id
                            ? {
                                ...tc,
                                status:
                                  event.data.status === "success"
                                    ? ("done" as const)
                                    : ("error" as const),
                                output: event.data.output,
                              }
                            : tc,
                        ),
                      }
                    : m,
                ),
              );
              break;

            case "error":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content:
                          m.content + `\n\n**Error:** ${event.data.message}`,
                      }
                    : m,
                ),
              );
              break;

            case "done":
              break;
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          // User cancelled — no error to show
        } else {
          const errorMsg =
            err instanceof Error ? err.message : "Unknown error";
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + `\n\n**Error:** ${errorMsg}` }
                : m,
            ),
          );
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [isStreaming, threadId, agents],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const newThread = useCallback(() => {
    setMessages([]);
    setThreadId(null);
  }, []);

  return { messages, isStreaming, threadId, sendMessage, cancel, newThread };
}
