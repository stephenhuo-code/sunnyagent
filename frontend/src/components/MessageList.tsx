import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import type { Message } from "../types";

interface MessageListProps {
  messages: Message[];
  isStreaming: boolean;
}

export default function MessageList({ messages, isStreaming }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new content arrives (only if near bottom)
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const threshold = 150;
    const isNearBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight <
      threshold;
    if (isNearBottom) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="message-list empty" ref={containerRef}>
        <div className="welcome">
          <h2>Deep Research Agent</h2>
          <p>Ask any research question and the agent will search the web, analyze sources, and write a comprehensive report.</p>
          <div className="examples">
            <span>Try:</span>
            <em>"Compare React, Vue, and Svelte for building modern web apps"</em>
            <em>"What are the latest advances in quantum computing?"</em>
            <em>"Research the impact of AI on software engineering jobs"</em>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list" ref={containerRef}>
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      {isStreaming && (
        <div className="streaming-indicator">
          <span className="dot" />
          <span className="dot" />
          <span className="dot" />
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
