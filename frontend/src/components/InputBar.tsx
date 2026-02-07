import { useState, useRef, useCallback, useEffect } from "react";
import { Send, Square } from "lucide-react";
import type { Agent } from "../types";

interface InputBarProps {
  onSend: (message: string) => void;
  onCancel: () => void;
  isStreaming: boolean;
  agents: Agent[];
}

export default function InputBar({ onSend, onCancel, isStreaming, agents }: InputBarProps) {
  const [text, setText] = useState("");
  const [showMenu, setShowMenu] = useState(false);
  const [menuIndex, setMenuIndex] = useState(0);
  const [filteredAgents, setFilteredAgents] = useState<Agent[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Filter agents based on current /prefix
  useEffect(() => {
    if (text.startsWith("/")) {
      const prefix = text.slice(1).split(/\s/)[0].toLowerCase();
      // Only show menu when cursor is still in the command part (no space yet)
      if (!text.includes(" ")) {
        const matches = agents.filter((a) =>
          a.name.toLowerCase().startsWith(prefix),
        );
        setFilteredAgents(matches);
        setShowMenu(matches.length > 0);
        setMenuIndex(0);
        return;
      }
    }
    setShowMenu(false);
  }, [text, agents]);

  const selectAgent = useCallback(
    (name: string) => {
      setText(`/${name} `);
      setShowMenu(false);
      textareaRef.current?.focus();
    },
    [],
  );

  const handleSubmit = useCallback(() => {
    if (isStreaming) {
      onCancel();
      return;
    }
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [text, isStreaming, onSend, onCancel]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (showMenu) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setMenuIndex((i) => Math.min(i + 1, filteredAgents.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setMenuIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === "Tab" || e.key === "Enter") {
        e.preventDefault();
        if (filteredAgents[menuIndex]) {
          selectAgent(filteredAgents[menuIndex].name);
        }
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setShowMenu(false);
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

  return (
    <div className="input-bar-wrapper">
      {showMenu && (
        <div className="agent-menu" ref={menuRef}>
          {filteredAgents.map((agent, i) => (
            <button
              key={agent.name}
              className={`agent-menu-item ${i === menuIndex ? "active" : ""}`}
              onMouseDown={(e) => {
                e.preventDefault();
                selectAgent(agent.name);
              }}
              onMouseEnter={() => setMenuIndex(i)}
            >
              <span className="agent-menu-name">/{agent.name}</span>
              <span className="agent-menu-desc">{agent.description}</span>
            </button>
          ))}
        </div>
      )}
      <div className="input-bar">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question or type / to pick an agent..."
          rows={1}
          disabled={isStreaming}
        />
        <button
          className={`send-btn ${isStreaming ? "cancel" : ""}`}
          onClick={handleSubmit}
          title={isStreaming ? "Stop" : "Send"}
        >
          {isStreaming ? <Square size={18} /> : <Send size={18} />}
        </button>
      </div>
    </div>
  );
}
