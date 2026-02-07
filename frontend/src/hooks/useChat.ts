import { useCallback, useRef, useState } from "react";
import { createThread, streamChat } from "../api/client";
import type { Message, ThinkingState, ToolCall } from "../types";

let msgCounter = 0;
function nextId() {
  return `msg-${++msgCounter}`;
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (text: string, agent?: string) => {
      if (isStreaming || !text.trim()) return;

      // Create thread on first message
      let currentThreadId = threadId;
      if (!currentThreadId) {
        currentThreadId = await createThread();
        setThreadId(currentThreadId);
      }

      const actualMessage = text.trim();

      // Add user message
      const userMsg: Message = { id: nextId(), role: "user", content: actualMessage };
      setMessages((prev) => [...prev, userMsg]);

      // Prepare assistant message placeholder
      const assistantId = nextId();
      const thinkingStart: ThinkingState = {
        steps: [],
        isThinking: true,
        startTime: Date.now(),
        durationSeconds: 0,
      };
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        toolCalls: [],
        thinking: thinkingStart,
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
                prev.map((m) => {
                  if (m.id !== assistantId) return m;
                  const updatedThinking =
                    m.thinking?.isThinking
                      ? {
                          ...m.thinking,
                          isThinking: false,
                          durationSeconds: Math.round(
                            (Date.now() - m.thinking.startTime) / 1000,
                          ),
                        }
                      : m.thinking;
                  return {
                    ...m,
                    content: m.content + event.data.text,
                    thinking: updatedThinking,
                  };
                }),
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

            case "thinking":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        thinking: {
                          ...(m.thinking ?? {
                            steps: [],
                            isThinking: true,
                            startTime: Date.now(),
                            durationSeconds: 0,
                          }),
                          steps: [
                            ...(m.thinking?.steps ?? []),
                            event.data.content,
                          ],
                        },
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
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== assistantId) return m;
                  if (m.thinking?.isThinking) {
                    return {
                      ...m,
                      thinking: {
                        ...m.thinking,
                        isThinking: false,
                        durationSeconds: Math.round(
                          (Date.now() - m.thinking.startTime) / 1000,
                        ),
                      },
                    };
                  }
                  return m;
                }),
              );
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
    [isStreaming, threadId],
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
