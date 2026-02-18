import { useEffect, useState, useRef } from "react";
import { useChat } from "../hooks/useChat";
import { getAgents, getSkills } from "../api/client";
import type { Agent, Skill, FileAttachment } from "../types";
import MessageList from "./MessageList";
import InputBar from "./InputBar";
import FilePreviewPanel from "./FilePreviewPanel";

interface ProjectContext {
  projectId: string;
  projectName: string;
  selectedFileCount: number;
}

interface ChatContainerProps {
  initialThreadId?: string | null;
  selectedFileIds?: string[];
  projectContext?: ProjectContext;
  onConversationCreated?: () => void;
  /** Optional initial message to send immediately after component mounts */
  initialMessage?: string | null;
}

export default function ChatContainer({
  initialThreadId,
  selectedFileIds = [],
  projectContext,
  onConversationCreated,
  initialMessage,
}: ChatContainerProps) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [previewFile, setPreviewFile] = useState<FileAttachment | null>(null);
  const initialMessageSentRef = useRef(false);

  useEffect(() => {
    getAgents().then(setAgents).catch(() => {});
    getSkills().then(setSkills).catch(() => {});
  }, []);

  const { messages, isStreaming, threadId, sendMessage, cancel, loadThread } =
    useChat({ onConversationCreated });

  // Load thread history if initialThreadId is provided
  useEffect(() => {
    if (initialThreadId) {
      loadThread(initialThreadId);
    }
  }, [initialThreadId, loadThread]);

  // Send initial message if provided (only once)
  useEffect(() => {
    if (initialMessage && !initialMessageSentRef.current && !isStreaming) {
      initialMessageSentRef.current = true;
      // Send with project context if available
      sendMessage(
        initialMessage,
        undefined,
        undefined,
        selectedFileIds.length > 0 ? selectedFileIds : undefined,
        projectContext?.projectId
      );
    }
  }, [initialMessage, isStreaming, sendMessage, selectedFileIds, projectContext]);

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
          projectFileCount={projectContext?.selectedFileCount}
          projectFileIds={selectedFileIds}
          projectId={projectContext?.projectId}
        />
      </div>

      <FilePreviewPanel
        file={previewFile}
        onClose={() => setPreviewFile(null)}
      />
    </div>
  );
}
