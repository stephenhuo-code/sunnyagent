import { useState, useRef, useCallback, useEffect } from "react";
import { Send, Square, Search, Database, Sparkles, Bot, X, Plus, Paperclip, FileText, File } from "lucide-react";
import type { Agent, Command, UploadingFile, UploadedFile, ProjectFile } from "../types";
import { uploadFile } from "../api/client";

const ICONS: Record<string, React.ComponentType<{ size?: number }>> = {
  search: Search,
  database: Database,
  sparkles: Sparkles,
  bot: Bot,
};

const AGENT_LABELS: Record<string, string> = {
  research: "深度研究",
  sql: "数据库",
};

const ALLOWED_EXTENSIONS = [
  ".txt", ".md", ".json", ".csv",  // 文本文件
  ".pdf",                           // PDF
  ".doc", ".docx",                  // Word
  ".ppt", ".pptx",                  // PowerPoint
  ".xls", ".xlsx",                  // Excel
];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface InputBarProps {
  onSend: (message: string, agent?: string, uploadedFiles?: UploadedFile[], projectFileIds?: string[], projectId?: string) => void;
  onCancel: () => void;
  isStreaming: boolean;
  agents: Agent[];
  commands: Command[];
  projectFiles?: ProjectFile[];
  onRemoveProjectFile?: (fileId: string) => void;
  projectFileIds?: string[];
  projectId?: string;
  /** Upload file to project (when in project context) */
  onUploadToProject?: (projectId: string, file: File) => Promise<void>;
}

export default function InputBar({ onSend, onCancel, isStreaming, agents, commands, projectFiles, onRemoveProjectFile, projectFileIds, projectId, onUploadToProject }: InputBarProps) {
  const [text, setText] = useState("");
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [showCommandSuggestions, setShowCommandSuggestions] = useState(false);
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0);
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const addMenuRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Get completed files
  const completedFiles = uploadingFiles.filter(f => f.status === "completed" && f.uploadedFile);

  // Note: File uploads are now handled by AIME's generic actor
  // No need to auto-select an agent - the system will route appropriately

  // Handle file selection
  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    setShowAddMenu(false);

    for (const file of Array.from(files)) {
      // Validate extension
      const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        alert(`不支持的文件类型: ${ext}。支持的类型: ${ALLOWED_EXTENSIONS.join(", ")}`);
        continue;
      }

      // Validate size
      if (file.size > MAX_FILE_SIZE) {
        alert(`文件过大: ${file.name}。最大支持: 10MB`);
        continue;
      }

      // If in project context, upload to project files (permanent storage)
      if (projectId && onUploadToProject) {
        try {
          await onUploadToProject(projectId, file);
        } catch (err) {
          alert(`上传失败: ${err instanceof Error ? err.message : "Unknown error"}`);
        }
        continue;
      }

      // Otherwise, upload as temporary file (existing logic)
      const uploadId = `upload-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const uploadingFile: UploadingFile = {
        id: uploadId,
        file,
        progress: 0,
        status: "uploading",
      };

      setUploadingFiles(prev => [...prev, uploadingFile]);

      try {
        const uploaded = await uploadFile(file, (progress) => {
          setUploadingFiles(prev =>
            prev.map(f => f.id === uploadId ? { ...f, progress } : f)
          );
        });

        setUploadingFiles(prev =>
          prev.map(f => f.id === uploadId
            ? { ...f, status: "completed" as const, progress: 100, uploadedFile: uploaded }
            : f
          )
        );
      } catch (err) {
        setUploadingFiles(prev =>
          prev.map(f => f.id === uploadId
            ? { ...f, status: "error" as const, error: err instanceof Error ? err.message : "Upload failed" }
            : f
          )
        );
      }
    }

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, [projectId, onUploadToProject]);

  // Remove an uploading file
  const removeUploadingFile = useCallback((id: string) => {
    setUploadingFiles(prev => prev.filter(f => f.id !== id));
  }, []);

  // Filter commands based on input after "/"
  const getFilteredCommands = useCallback(() => {
    if (!text.startsWith("/")) return [];
    const query = text.slice(1).toLowerCase();
    return commands.filter(
      (cmd) =>
        cmd.name.toLowerCase().includes(query) ||
        cmd.description.toLowerCase().includes(query)
    );
  }, [text, commands]);

  const filteredCommands = getFilteredCommands();

  // Show suggestions when text starts with "/" and there are matching commands
  useEffect(() => {
    if (text.startsWith("/") && filteredCommands.length > 0) {
      setShowCommandSuggestions(true);
      setSelectedCommandIndex(0);
    } else {
      setShowCommandSuggestions(false);
    }
  }, [text, filteredCommands.length]);

  // Handle click outside to close add menu
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (addMenuRef.current && !addMenuRef.current.contains(e.target as Node)) {
        setShowAddMenu(false);
      }
    };
    if (showAddMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showAddMenu]);

  const selectCommand = useCallback((commandName: string) => {
    setText(`/${commandName} `);
    setShowCommandSuggestions(false);
    textareaRef.current?.focus();
  }, []);

  const handleSubmit = useCallback(() => {
    if (isStreaming) {
      onCancel();
      return;
    }
    const trimmed = text.trim();
    // Allow sending with just files (no text required) - either uploaded files or project files
    const hasProjectFiles = projectFileIds && projectFileIds.length > 0;
    if (!trimmed && completedFiles.length === 0 && !hasProjectFiles) return;

    const filesToSend = completedFiles.map(f => f.uploadedFile!);
    onSend(
      trimmed,
      selectedAgent ?? undefined,
      filesToSend.length > 0 ? filesToSend : undefined,
      hasProjectFiles ? projectFileIds : undefined,
      projectId
    );
    setText("");
    setUploadingFiles([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [text, isStreaming, onSend, onCancel, selectedAgent, completedFiles, projectFileIds, projectId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // 忽略 IME 输入法组合过程中的回车（用于选择候选词）
    if (e.nativeEvent.isComposing) {
      return;
    }

    // Handle command suggestions navigation
    if (showCommandSuggestions && filteredCommands.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedCommandIndex((prev) =>
          prev < filteredCommands.length - 1 ? prev + 1 : 0
        );
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedCommandIndex((prev) =>
          prev > 0 ? prev - 1 : filteredCommands.length - 1
        );
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        selectCommand(filteredCommands[selectedCommandIndex].name);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setShowCommandSuggestions(false);
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  };

  const selectedAgentData = agents.find((a) => a.name === selectedAgent);
  const SelectedIcon = selectedAgentData ? ICONS[selectedAgentData.icon] ?? Bot : null;

  return (
    <div className="input-bar-wrapper">
      {/* Agent selector chips - hidden when an agent is selected */}
      {!selectedAgent && (
        <div className="agent-selector">
          {[...agents].sort((a, b) => a.name.localeCompare(b.name)).map((agent) => {
            const AgentIcon = ICONS[agent.icon] ?? Bot;
            const label = AGENT_LABELS[agent.name] ?? agent.name;
            return (
              <button
                key={agent.name}
                className="agent-chip"
                onClick={() => setSelectedAgent(agent.name)}
                title={agent.description}
              >
                <AgentIcon size={16} />
                <span>{label}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Input area with toolbar inside */}
      <div className="input-area">
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept={ALLOWED_EXTENSIONS.join(",")}
          multiple
          onChange={handleFileSelect}
          style={{ display: "none" }}
        />

        {/* Uploaded files display inside input area */}
        {uploadingFiles.length > 0 && (
          <div className="input-files">
            {uploadingFiles.map((item) => (
              <div key={item.id} className={`input-file-card ${item.status}`}>
                <div className="input-file-icon">
                  <FileText size={20} />
                </div>
                <div className="input-file-info">
                  <span className="input-file-name">{item.file.name.replace(/\.[^/.]+$/, "")}</span>
                  <span className="input-file-meta">
                    {item.file.name.slice(item.file.name.lastIndexOf(".") + 1).toUpperCase()} · {formatSize(item.file.size)}
                    {item.status === "uploading" && ` · ${item.progress}%`}
                  </span>
                </div>
                <button
                  className="input-file-remove"
                  onClick={() => removeUploadingFile(item.id)}
                  title="移除"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Selected project files display */}
        {projectFiles && projectFiles.length > 0 && (
          <div className="selected-project-files">
            {projectFiles.map((file) => (
              <div key={file.file_id} className="selected-file-chip">
                <File size={14} className="selected-file-icon" />
                <span className="selected-file-name" title={file.original_name}>
                  {file.original_name}
                </span>
                <button
                  className="selected-file-remove"
                  onClick={() => onRemoveProjectFile?.(file.file_id)}
                  title="取消选择"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Command suggestions dropdown */}
        {showCommandSuggestions && filteredCommands.length > 0 && (
          <div className="command-suggestions" ref={suggestionsRef}>
            {filteredCommands.map((cmd, index) => (
              <div
                key={cmd.name}
                className={`command-suggestion-item ${index === selectedCommandIndex ? "selected" : ""}`}
                onClick={() => selectCommand(cmd.name)}
                onMouseEnter={() => setSelectedCommandIndex(index)}
              >
                <span className="command-name">/{cmd.name}</span>
                {cmd.argument_hint && (
                  <span className="command-hint">{cmd.argument_hint}</span>
                )}
                <span className="command-description">{cmd.description}</span>
              </div>
            ))}
          </div>
        )}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={
            projectFiles && projectFiles.length > 0
              ? `已选择 ${projectFiles.length} 个文件，输入问题...`
              : completedFiles.length > 0
                ? "文件已就绪，输入消息一起发送..."
                : "输入问题..."
          }
          rows={1}
          disabled={isStreaming}
        />
        {/* Toolbar inside the input box */}
        <div className="input-toolbar">
          {/* Left: add button, selected agent indicator and skill button */}
          <div className="toolbar-left">
            {/* Add file button */}
            <div className="add-button-wrapper" ref={addMenuRef}>
              <button
                className="toolbar-btn"
                onClick={() => setShowAddMenu(!showAddMenu)}
                title="添加文件"
              >
                <Plus size={18} />
              </button>

              {showAddMenu && (
                <div className="add-menu">
                  <button
                    className="add-menu-item"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Paperclip size={16} />
                    <span>从本地添加文件</span>
                  </button>
                </div>
              )}
            </div>

            {selectedAgentData && SelectedIcon && (
              <button
                className="agent-chip selected"
                onClick={() => setSelectedAgent(null)}
              >
                <SelectedIcon size={16} />
                <span>{AGENT_LABELS[selectedAgentData.name] ?? selectedAgentData.name}</span>
                <X size={12} />
              </button>
            )}
          </div>

          {/* Right: send button */}
          <button
            className={`send-btn ${isStreaming ? "cancel" : ""}`}
            onClick={handleSubmit}
            title={isStreaming ? "停止" : "发送"}
          >
            {isStreaming ? <Square size={18} /> : <Send size={18} />}
          </button>
        </div>
      </div>
    </div>
  );
}
