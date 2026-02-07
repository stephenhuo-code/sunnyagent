import Markdown from "react-markdown";
import { User, Bot } from "lucide-react";
import ToolCallCard from "./ToolCallCard";
import ThinkingBubble from "./ThinkingBubble";
import type { Message } from "../types";

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`message-bubble ${isUser ? "user" : "assistant"}`}>
      <div className="message-avatar">
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>
      <div className="message-body">
        {/* Thinking bubble (shown before tool calls and content) */}
        {message.thinking &&
          (message.thinking.isThinking ||
            message.thinking.steps.length > 0) && (
            <ThinkingBubble thinking={message.thinking} />
          )}
        {/* Tool calls (excluding think_tool which is in the thinking bubble) */}
        {message.toolCalls
          ?.filter((tc) => tc.name !== "think_tool")
          .map((tc) => <ToolCallCard key={tc.id} toolCall={tc} />)}
        {message.content && (
          <div className="message-content">
            {isUser ? (
              <p>{message.content}</p>
            ) : (
              <Markdown>{message.content}</Markdown>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
