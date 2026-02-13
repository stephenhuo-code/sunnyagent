import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import type { Message, FileAttachment } from "../types";

interface MessageListProps {
  messages: Message[];
  isStreaming: boolean;
  scrollKey?: string | number;
  onFileClick?: (file: FileAttachment) => void;
}

export default function MessageList({ messages, isStreaming, scrollKey, onFileClick }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  // If scrollKey is provided on mount, we need to scroll when messages load
  const needsScroll = useRef(!!scrollKey);

  // Scroll when messages are loaded and we need to scroll
  useEffect(() => {
    if (needsScroll.current && messages.length > 0) {
      needsScroll.current = false;
      setTimeout(() => {
        bottomRef.current?.scrollIntoView({ behavior: "auto" });
      }, 0);
    }
  }, [messages]);

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
          <h2>Sunny Agents</h2>
          <p>提出任何研究问题，智能体将搜索网络、分析来源并撰写综合报告。</p>
          <div className="examples">
            <span>试试:</span>
            <em>"比较 React、Vue 和 Svelte 构建现代 Web 应用"</em>
            <em>"量子计算的最新进展是什么？"</em>
            <em>"研究 AI 对软件工程岗位的影响"</em>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list" ref={containerRef}>
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} onFileClick={onFileClick} />
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
