import { useEffect, useState } from "react";
import { useChat } from "../hooks/useChat";
import { getAgents, getSkills } from "../api/client";
import type { Agent, Skill, FileAttachment } from "../types";
import MessageList from "./MessageList";
import InputBar from "./InputBar";
import FilePreviewPanel from "./FilePreviewPanel";
import { RotateCcw } from "lucide-react";

export default function ChatContainer() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [previewFile, setPreviewFile] = useState<FileAttachment | null>(null);

  useEffect(() => {
    getAgents().then(setAgents).catch(() => {});
    getSkills().then(setSkills).catch(() => {});
  }, []);

  const { messages, isStreaming, threadId, sendMessage, cancel, newThread } =
    useChat();

  return (
    <div className={`chat-layout ${previewFile ? "with-preview" : ""}`}>
      <div className="chat-container">
        <header className="chat-header">
          <h1>Sunny Agents</h1>
          {threadId && (
            <span className="thread-id">Thread: {threadId}</span>
          )}
          <button className="new-thread-btn" onClick={newThread} title="New thread">
            <RotateCcw size={16} />
            New
          </button>
        </header>
        <MessageList
          messages={messages}
          isStreaming={isStreaming}
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
