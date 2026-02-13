import { useEffect, useState } from "react";
import { useChat } from "../hooks/useChat";
import { getAgents, getSkills } from "../api/client";
import type { Agent, Skill, FileAttachment } from "../types";
import MessageList from "./MessageList";
import InputBar from "./InputBar";
import FilePreviewPanel from "./FilePreviewPanel";

interface ChatContainerProps {
  initialThreadId?: string | null;
}

export default function ChatContainer({ initialThreadId }: ChatContainerProps) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [previewFile, setPreviewFile] = useState<FileAttachment | null>(null);

  useEffect(() => {
    getAgents().then(setAgents).catch(() => {});
    getSkills().then(setSkills).catch(() => {});
  }, []);

  const { messages, isStreaming, threadId, sendMessage, cancel, loadThread } =
    useChat();

  // Load thread history if initialThreadId is provided
  useEffect(() => {
    if (initialThreadId) {
      loadThread(initialThreadId);
    }
  }, [initialThreadId, loadThread]);

  return (
    <div className={`chat-layout ${previewFile ? "with-preview" : ""}`}>
      <div className="chat-container">
        <header className="chat-header">
          <h1>Sunny Agents</h1>
          {threadId && (
            <span className="thread-id">线程: {threadId}</span>
          )}
        </header>
        <MessageList
          messages={messages}
          isStreaming={isStreaming}
          scrollKey={initialThreadId ?? undefined}
          onFileClick={setPreviewFile}
        />
        <InputBar
          onSend={sendMessage}
          onCancel={cancel}
          isStreaming={isStreaming}
          agents={agents}
          skills={skills}
        />
      </div>

      <FilePreviewPanel
        file={previewFile}
        onClose={() => setPreviewFile(null)}
      />
    </div>
  );
}
