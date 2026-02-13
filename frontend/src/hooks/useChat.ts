import { useCallback, useRef, useState } from "react";
import { createThread, streamChat, getThreadHistory } from "../api/client";
import type { Message, ThinkingState, ToolCall, UploadedFile, DisplayScenario, SpawnedTask } from "../types";

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
        // Start with "agent" scenario to show ThinkingBubble immediately
        displayScenario: "agent" as DisplayScenario,
        spawnedTasks: [],
        todos: [],
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
              // Accumulate text_delta only in message.content (Layer 3)
              // ThinkingBubble only shows thinking steps, not the actual response
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + event.data.text }
                    : m
                ),
              );
              break;

            case "tool_call_start": {
              console.log(`[TOOL_START] id=${event.data.id}, name=${event.data.name}, task_id=${event.data.task_id}`, event.data.args);
              const tc: ToolCall = {
                id: event.data.id,
                name: event.data.name,
                args: event.data.args,
                status: "running",
              };
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== assistantId) return m;
                  // If tool has a task_id, associate it with the spawned task
                  const taskId = event.data.task_id;
                  if (taskId && m.spawnedTasks) {
                    return {
                      ...m,
                      spawnedTasks: m.spawnedTasks.map((task) =>
                        task.task_id === taskId
                          ? { ...task, toolCalls: [...task.toolCalls, tc] }
                          : task
                      ),
                    };
                  }
                  // Otherwise add to top-level toolCalls
                  return { ...m, toolCalls: [...(m.toolCalls ?? []), tc] };
                }),
              );
              break;
            }

            case "tool_call_result": {
              console.log(`[TOOL_RESULT] id=${event.data.id}, status=${event.data.status}, task_id=${event.data.task_id}`, event.data.output?.slice(0, 200));
              const resultStatus = event.data.status === "success" ? "done" as const : "error" as const;
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== assistantId) return m;
                  // If tool has a task_id, update in spawned task
                  const taskId = event.data.task_id;
                  if (taskId && m.spawnedTasks) {
                    return {
                      ...m,
                      spawnedTasks: m.spawnedTasks.map((task) =>
                        task.task_id === taskId
                          ? {
                              ...task,
                              toolCalls: task.toolCalls.map((tc) =>
                                tc.id === event.data.id
                                  ? { ...tc, status: resultStatus, output: event.data.output }
                                  : tc
                              ),
                            }
                          : task
                      ),
                    };
                  }
                  // Otherwise update in top-level toolCalls
                  return {
                    ...m,
                    toolCalls: (m.toolCalls ?? []).map((tc) =>
                      tc.id === event.data.id
                        ? { ...tc, status: resultStatus, output: event.data.output }
                        : tc
                    ),
                  };
                }),
              );
              break;
            }

            case "thinking":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        // Upgrade scenario: any thinking event upgrades quick → agent
                        // planning/replanning explicitly upgrades to planning
                        displayScenario: event.data.type === "planning" || event.data.type === "replanning"
                          ? "planning" as DisplayScenario
                          : m.displayScenario === "quick"
                            ? "agent" as DisplayScenario
                            : m.displayScenario,
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

            case "todos_updated": {
              console.log(`[TODOS_UPDATED] count=${event.data.todos.length}`, event.data.todos);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        // Upgrade to planning scenario when we receive todos
                        displayScenario: "planning" as DisplayScenario,
                        todos: event.data.todos,
                      }
                    : m,
                ),
              );
              break;
            }

            case "task_spawned": {
              console.log(`[TASK_SPAWNED] task_id=${event.data.task_id}, type=${event.data.subagent_type}`, event.data.description);
              const newTask: SpawnedTask = {
                task_id: event.data.task_id,
                subagent_type: event.data.subagent_type,
                description: event.data.description,
                status: "running",
                toolCalls: [],
              };
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        // Upgrade to agent scenario when we see task_spawned
                        displayScenario: m.displayScenario === "planning" ? "planning" : "agent" as DisplayScenario,
                        spawnedTasks: [...(m.spawnedTasks ?? []), newTask],
                      }
                    : m,
                ),
              );
              break;
            }

            case "task_completed": {
              console.log(`[TASK_COMPLETED] task_id=${event.data.task_id}, status=${event.data.status}, duration=${event.data.duration_ms}ms`);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        spawnedTasks: (m.spawnedTasks ?? []).map((task) =>
                          task.task_id === event.data.task_id
                            ? {
                                ...task,
                                status: event.data.status,
                                duration_ms: event.data.duration_ms,
                              }
                            : task
                        ),
                      }
                    : m,
                ),
              );
              break;
            }

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

                  // No longer degrade to quick - always keep agent/planning scenario
                  // ThinkingBubble shows streaming content and collapses on completion

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
