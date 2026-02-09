import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { Send, Square, Search, Database, Sparkles, Bot, X, Puzzle, Plus, Paperclip, FileText } from "lucide-react";
import type { Agent, Skill, UploadingFile, UploadedFile } from "../types";
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
  general: "通用",
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
  onSend: (message: string, agent?: string, uploadedFiles?: UploadedFile[]) => void;
  onCancel: () => void;
  isStreaming: boolean;
  agents: Agent[];
  skills: Skill[];
}

export default function InputBar({ onSend, onCancel, isStreaming, agents, skills }: InputBarProps) {
  const [text, setText] = useState("");
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [showSkillSuggestions, setShowSkillSuggestions] = useState(false);
  const [selectedSkillIndex, setSelectedSkillIndex] = useState(0);
  const [showSkillPopover, setShowSkillPopover] = useState(false);
  const [skillSearch, setSkillSearch] = useState("");
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const addMenuRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Get completed files
  const completedFiles = uploadingFiles.filter(f => f.status === "completed" && f.uploadedFile);

  // Auto-select general agent when files are uploaded (only general agent has read_uploaded_file tool)
  useEffect(() => {
    if (completedFiles.length > 0 && !selectedAgent) {
      setSelectedAgent("general");
    }
  }, [completedFiles.length, selectedAgent]);

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
  }, []);

  // Remove an uploading file
  const removeUploadingFile = useCallback((id: string) => {
    setUploadingFiles(prev => prev.filter(f => f.id !== id));
  }, []);

  // Filter skills based on input after "/"
  const getFilteredSkills = useCallback(() => {
    if (!text.startsWith("/")) return [];
    const query = text.slice(1).toLowerCase();
    return skills.filter(
      (skill) =>
        skill.name.toLowerCase().includes(query) ||
        skill.description.toLowerCase().includes(query)
    );
  }, [text, skills]);

  const filteredSkills = getFilteredSkills();

  // Filter skills for popover (search by name or description, limit to 5)
  const filteredPopoverSkills = skills.filter(
    (skill) =>
      skill.name.toLowerCase().includes(skillSearch.toLowerCase()) ||
      skill.description.toLowerCase().includes(skillSearch.toLowerCase())
  ).slice(0, 5);

  // Parse selected skills from input text
  const selectedSkillsFromText = useMemo(() => {
    const matches = text.match(/\/([a-zA-Z0-9_-]+)/g) || [];
    const skillNames = matches.map(m => m.slice(1)); // Remove leading "/"
    // Only keep skills that exist in the skills list
    return skillNames.filter(name =>
      skills.some(skill => skill.name === name)
    );
  }, [text, skills]);

  const selectedSkillCount = selectedSkillsFromText.length;

  // Show suggestions when text starts with "/" and there are matching skills
  useEffect(() => {
    if (text.startsWith("/") && filteredSkills.length > 0) {
      setShowSkillSuggestions(true);
      setSelectedSkillIndex(0);
    } else {
      setShowSkillSuggestions(false);
    }
  }, [text, filteredSkills.length]);

  // Handle click outside to close popover and add menu
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setShowSkillPopover(false);
      }
      if (addMenuRef.current && !addMenuRef.current.contains(e.target as Node)) {
        setShowAddMenu(false);
      }
    };
    if (showSkillPopover || showAddMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showSkillPopover, showAddMenu]);

  const selectSkill = useCallback((skillName: string) => {
    setText(`/${skillName} `);
    setShowSkillSuggestions(false);
    textareaRef.current?.focus();
  }, []);

  const handleSkillSelect = (skillName: string) => {
    // If skill is already in text, don't add it again
    if (selectedSkillsFromText.includes(skillName)) {
      setShowSkillPopover(false);
      setSkillSearch("");
      textareaRef.current?.focus();
      return;
    }
    // Append to end of text
    setText(prev => {
      const trimmed = prev.trimEnd();
      return trimmed ? `${trimmed} /${skillName} ` : `/${skillName} `;
    });
    setShowSkillPopover(false);
    setSkillSearch("");
    textareaRef.current?.focus();
  };

  const handleSubmit = useCallback(() => {
    if (isStreaming) {
      onCancel();
      return;
    }
    const trimmed = text.trim();
    // Allow sending with just files (no text required)
    if (!trimmed && completedFiles.length === 0) return;

    const filesToSend = completedFiles.map(f => f.uploadedFile!);
    onSend(trimmed, selectedAgent ?? undefined, filesToSend.length > 0 ? filesToSend : undefined);
    setText("");
    setUploadingFiles([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [text, isStreaming, onSend, onCancel, selectedAgent, completedFiles]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // 忽略 IME 输入法组合过程中的回车（用于选择候选词）
    if (e.nativeEvent.isComposing) {
      return;
    }

    // Handle skill suggestions navigation
    if (showSkillSuggestions && filteredSkills.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedSkillIndex((prev) =>
          prev < filteredSkills.length - 1 ? prev + 1 : 0
        );
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedSkillIndex((prev) =>
          prev > 0 ? prev - 1 : filteredSkills.length - 1
        );
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        selectSkill(filteredSkills[selectedSkillIndex].name);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setShowSkillSuggestions(false);
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
          {[...agents].sort((a, b) => {
            if (a.name === "general") return -1;
            if (b.name === "general") return 1;
            return 0;
          }).map((agent) => {
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

        {/* Skill suggestions dropdown */}
        {showSkillSuggestions && filteredSkills.length > 0 && (
          <div className="skill-suggestions" ref={suggestionsRef}>
            {filteredSkills.map((skill, index) => (
              <div
                key={skill.name}
                className={`skill-suggestion-item ${index === selectedSkillIndex ? "selected" : ""}`}
                onClick={() => selectSkill(skill.name)}
                onMouseEnter={() => setSelectedSkillIndex(index)}
              >
                <span className="skill-name">/{skill.name}</span>
                <span className="skill-description">{skill.description}</span>
              </div>
            ))}
          </div>
        )}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={completedFiles.length > 0 ? "文件已就绪，输入消息一起发送..." : "输入问题..."}
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

            {/* Skill selector button */}
            <div className="skill-button-wrapper" ref={popoverRef}>
              <button
                className={`toolbar-btn ${selectedSkillCount > 0 ? "has-selection" : ""}`}
                onClick={() => setShowSkillPopover(!showSkillPopover)}
                title="选择技能"
              >
                <Puzzle size={18} />
                {selectedSkillCount > 0 && (
                  <span className="skill-badge">{selectedSkillCount}</span>
                )}
              </button>

              {showSkillPopover && (
                <div className="skill-popover">
                  <div className="skill-popover-search">
                    <Search size={16} />
                    <input
                      type="text"
                      placeholder="搜索技能..."
                      value={skillSearch}
                      onChange={(e) => setSkillSearch(e.target.value)}
                      autoFocus
                    />
                  </div>
                  <div className="skill-popover-list">
                    {filteredPopoverSkills.map((skill) => {
                      const isSelected = selectedSkillsFromText.includes(skill.name);
                      return (
                        <div
                          key={skill.name}
                          className={`skill-popover-item ${isSelected ? "selected" : ""}`}
                          onClick={() => handleSkillSelect(skill.name)}
                        >
                          <div className="skill-popover-name">
                            <Puzzle size={14} />
                            {skill.name}
                            {isSelected && <span className="skill-check">✓</span>}
                          </div>
                          <div className="skill-popover-desc">{skill.description}</div>
                        </div>
                      );
                    })}
                    {filteredPopoverSkills.length === 0 && (
                      <div className="skill-popover-empty">未找到匹配的技能</div>
                    )}
                  </div>
                </div>
              )}
            </div>
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
