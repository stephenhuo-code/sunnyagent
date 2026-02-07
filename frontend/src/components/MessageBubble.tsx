import Markdown from "react-markdown";
import { User, Bot } from "lucide-react";
import ToolCallCard from "./ToolCallCard";
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
        {/* Tool calls before text content */}
        {message.toolCalls?.map((tc) => (
          <ToolCallCard key={tc.id} toolCall={tc} />
        ))}
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
