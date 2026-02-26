import { useEffect, useState, useRef, useCallback } from "react";
import { useChat } from "../hooks/useChat";
import { getAgents, getCommands } from "../api/client";
import type { Agent, Command, FileAttachment, ProjectFile } from "../types";
import MessageList from "./MessageList";
import InputBar from "./InputBar";
import FilePreviewPanel from "./FilePreviewPanel";
import HtmlViewerModal from "./HtmlViewerModal";

interface ProjectContext {
  projectId: string;
  projectName: string;
  selectedFileCount: number;
}

interface ChatContainerProps {
  initialThreadId?: string | null;
  selectedFileIds?: string[];
  projectFiles?: ProjectFile[];
  onToggleFileSelection?: (fileId: string) => void;
  projectContext?: ProjectContext;
  onConversationCreated?: () => void;
  /** Optional initial message to send immediately after component mounts */
  initialMessage?: string | null;
  /** Upload file to project (when in project context) */
  onUploadToProject?: (projectId: string, file: File) => Promise<void>;
}

export default function ChatContainer({
  initialThreadId,
  selectedFileIds = [],
  projectFiles = [],
  onToggleFileSelection,
  projectContext,
  onConversationCreated,
  initialMessage,
  onUploadToProject,
}: ChatContainerProps) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [commands, setCommands] = useState<Command[]>([]);
  const [previewFile, setPreviewFile] = useState<FileAttachment | null>(null);
  const [htmlViewerFile, setHtmlViewerFile] = useState<FileAttachment | null>(null);
  const initialMessageSentRef = useRef(false);

  // Handle file click - route HTML files to modal, others to side panel
  const handleFileClick = useCallback((file: FileAttachment) => {
    const ext = file.filename.toLowerCase().slice(file.filename.lastIndexOf("."));
    if (ext === ".html" || ext === ".htm") {
      setHtmlViewerFile(file);  // HTML files use modal
    } else {
      setPreviewFile(file);     // Other files use side panel
    }
  }, []);

  useEffect(() => {
    getAgents().then(setAgents).catch(() => {});
    getCommands().then(setCommands).catch(() => {});
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
          onFileClick={handleFileClick}
        />
        <InputBar
          onSend={sendMessage}
          onCancel={cancel}
          isStreaming={isStreaming}
          agents={agents}
          commands={commands}
          projectFiles={projectFiles.filter(f => selectedFileIds.includes(f.file_id))}
          onRemoveProjectFile={onToggleFileSelection}
          projectFileIds={selectedFileIds}
          projectId={projectContext?.projectId}
          onUploadToProject={onUploadToProject}
        />
      </div>

      <FilePreviewPanel
        file={previewFile}
        onClose={() => setPreviewFile(null)}
      />

      <HtmlViewerModal
        file={htmlViewerFile}
        onClose={() => setHtmlViewerFile(null)}
      />
    </div>
  );
}
