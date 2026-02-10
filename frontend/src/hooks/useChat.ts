import { useCallback, useRef, useState } from "react";
import { createThread, streamChat, getThreadHistory } from "../api/client";
import type { Message, ThinkingState, ToolCall, UploadedFile } from "../types";

let msgCounter = 0;
function nextId() {
  return `msg-${++msgCounter}`;
}

/**
 * Parse slash commands from message text.
 * Returns skill name if message starts with /skillname, otherwise null.
 * Agent-style commands (like /research) are handled separately.
 */
function parseSkillCommand(text: string): { skill: string | null; message: string } {
  const trimmed = text.trim();
  const match = trimmed.match(/^\/([a-z0-9-]+)\s*(.*)/i);
  if (!match) {
    return { skill: null, message: trimmed };
  }
  return { skill: match[1].toLowerCase(), message: match[2] || trimmed };
}

interface UseChatOptions {
  initialThreadId?: string | null;
}

export function useChat(options: UseChatOptions = {}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(options.initialThreadId ?? null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (text: string, agent?: string, uploadedFiles?: UploadedFile[]) => {
      if (isStreaming) return;
      // Allow sending with files even if text is empty
      if (!text.trim() && (!uploadedFiles || uploadedFiles.length === 0)) return;

      // Create thread on first message
      let currentThreadId = threadId;
      if (!currentThreadId) {
        currentThreadId = await createThread();
        setThreadId(currentThreadId);
      }

      // Parse /skill commands (only if no agent explicitly specified)
      const { skill, message: parsedMessage } = agent ? { skill: null, message: text.trim() } : parseSkillCommand(text);
      const actualMessage = text.trim();

      // Add user message with file attachments
      const userMsg: Message = {
        id: nextId(),
        role: "user",
        content: actualMessage,
        files: uploadedFiles?.map(f => ({
          file_id: f.file_id,
          filename: f.filename,
          size: f.size,
          content_type: f.content_type,
          source: "user" as const,
          download_url: f.download_url,
        })),
      };
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

      // Collect file IDs to send
      const fileIds = uploadedFiles?.map(f => f.file_id);

      try {
        for await (const event of streamChat(
          currentThreadId,
          skill ? parsedMessage : actualMessage,
          controller.signal,
          agent,
          skill ?? undefined,
          fileIds,
        )) {
          console.log(`[CHAT_EVENT] event=${event.event}`, event.data);
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
              console.log(`[TOOL_START] id=${event.data.id}, name=${event.data.name}`, event.data.args);
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
              console.log(`[TOOL_RESULT] id=${event.data.id}, status=${event.data.status}`, event.data.output?.slice(0, 200));
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

  const loadThread = useCallback(async (newThreadId: string) => {
    setThreadId(newThreadId);
    setMessages([]);

    try {
      const history = await getThreadHistory(newThreadId);
      if (history.messages && history.messages.length > 0) {
        const loadedMessages: Message[] = history.messages.map((msg: { role: string; content: string }, index: number) => ({
          id: `history-${index}`,
          role: msg.role as "user" | "assistant",
          content: msg.content,
        }));
        setMessages(loadedMessages);
      }
    } catch (err) {
      console.error("Failed to load thread history:", err);
    }
  }, []);

  return { messages, isStreaming, threadId, sendMessage, cancel, newThread, loadThread };
}
