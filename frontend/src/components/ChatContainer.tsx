import { useEffect, useState } from "react";
import { useChat } from "../hooks/useChat";
import { getAgents } from "../api/client";
import type { Agent } from "../types";
import MessageList from "./MessageList";
import InputBar from "./InputBar";
import { RotateCcw } from "lucide-react";

export default function ChatContainer() {
  const [agents, setAgents] = useState<Agent[]>([]);

  useEffect(() => {
    getAgents().then(setAgents).catch(() => {});
  }, []);

  const { messages, isStreaming, threadId, sendMessage, cancel, newThread } =
    useChat(agents);

  return (
    <div className="chat-container">
      <header className="chat-header">
        <h1>Deep Research</h1>
        {threadId && (
          <span className="thread-id">Thread: {threadId}</span>
        )}
        <button className="new-thread-btn" onClick={newThread} title="New thread">
          <RotateCcw size={16} />
          New
        </button>
      </header>
      <MessageList messages={messages} isStreaming={isStreaming} />
      <InputBar
        onSend={sendMessage}
        onCancel={cancel}
        isStreaming={isStreaming}
        agents={agents}
      />
    </div>
  );
}
