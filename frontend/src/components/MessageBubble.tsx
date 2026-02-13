import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User, Bot } from "lucide-react";
import ToolCallCard from "./ToolCallCard";
import ThinkingBubble from "./ThinkingBubble";
import FileCard from "./FileCard";
import TaskList from "./TaskList";
import type { Message, FileAttachment } from "../types";

interface MessageBubbleProps {
  message: Message;
  onFileClick?: (file: FileAttachment) => void;
}

export default function MessageBubble({ message, onFileClick }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const scenario = message.displayScenario ?? "quick";

  // Determine what to show based on scenario
  // Show thinking for both "agent" and "planning" scenarios
  const showThinking = (scenario === "agent" || scenario === "planning") &&
    message.thinking &&
    (message.thinking.isThinking || message.thinking.steps.length > 0);
  const showTaskTree = (scenario === "agent" || scenario === "planning") &&
    ((message.spawnedTasks && message.spawnedTasks.length > 0) ||
     (message.todos && message.todos.length > 0));
  const showTopLevelToolCalls = scenario === "quick" && message.toolCalls &&
    message.toolCalls.filter((tc) => tc.name !== "think_tool").length > 0;

  return (
    <div className={`message-bubble ${isUser ? "user" : "assistant"}`}>
      <div className="message-avatar">
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>
      <div className="message-body">
        {/* File attachments for user messages */}
        {isUser && message.files && message.files.length > 0 && (
          <div className="message-files">
            {message.files.map((file) => (
              <FileCard
                key={file.file_id}
                file={file}
                onClick={() => onFileClick?.(file)}
              />
            ))}
          </div>
        )}

        {/* === Three-Layer Display Structure === */}

        {/* Layer 1: Thinking Bubble (only for planning scenario) */}
        {showThinking && message.thinking && (
          <ThinkingBubble thinking={message.thinking} />
        )}

        {/* Layer 2: Task Tree (for agent/planning scenarios) */}
        {showTaskTree && (
          <TaskList
            todos={message.todos}
            spawnedTasks={message.spawnedTasks}
          />
        )}

        {/* Layer 2 (fallback): Top-level tool calls for quick scenario */}
        {showTopLevelToolCalls && message.toolCalls
          ?.filter((tc) => tc.name !== "think_tool")
          .map((tc) => <ToolCallCard key={tc.id} toolCall={tc} />)}

        {/* Layer 3: Result Area (content) - always show when there's content */}
        {message.content && (
          <div className="message-content">
            {isUser ? (
              <p>{message.content}</p>
            ) : (
              <Markdown remarkPlugins={[remarkGfm]}>{message.content}</Markdown>
            )}
          </div>
        )}

        {/* File attachments for assistant messages (after content) */}
        {!isUser && message.files && message.files.length > 0 && (
          <div className="message-files">
            {message.files.map((file) => (
              <FileCard
                key={file.file_id}
                file={file}
                onClick={() => onFileClick?.(file)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
