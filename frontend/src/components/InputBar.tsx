import { useState, useRef, useCallback } from "react";
import { Send, Square, Search, Database, Sparkles, Bot, X } from "lucide-react";
import type { Agent } from "../types";

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

interface InputBarProps {
  onSend: (message: string, agent?: string) => void;
  onCancel: () => void;
  isStreaming: boolean;
  agents: Agent[];
}

export default function InputBar({ onSend, onCancel, isStreaming, agents }: InputBarProps) {
  const [text, setText] = useState("");
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    if (isStreaming) {
      onCancel();
      return;
    }
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed, selectedAgent ?? undefined);
    setText("");
    setSelectedAgent(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [text, isStreaming, onSend, onCancel, selectedAgent]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
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
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question..."
          rows={1}
          disabled={isStreaming}
        />
        {/* Toolbar inside the input box */}
        <div className="input-toolbar">
          {/* Left: selected agent indicator */}
          <div className="toolbar-left">
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
            title={isStreaming ? "Stop" : "Send"}
          >
            {isStreaming ? <Square size={18} /> : <Send size={18} />}
          </button>
        </div>
      </div>
    </div>
  );
}
