/**
 * Floating popover for conversation list when sidebar is collapsed
 */

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { ConversationItem } from "./ConversationItem";
import type { ConversationSummary } from "../../api/conversations";
import "./Conversations.css";

interface ConversationPopoverProps {
  conversations: ConversationSummary[];
  isLoading: boolean;
  error: string | null;
  selectedId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  onUpdate: (id: string, title: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

export function ConversationPopover({
  conversations,
  isLoading,
  error,
  selectedId,
  isOpen,
  onClose,
  onSelect,
  onUpdate,
  onDelete,
}: ConversationPopoverProps) {
  const popoverRef = useRef<HTMLDivElement>(null);

  // Handle click outside to close
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(event.target as Node)
      ) {
        onClose();
      }
    };

    // Add listener with a small delay to prevent immediate close
    const timeoutId = setTimeout(() => {
      document.addEventListener("mousedown", handleClickOutside);
    }, 0);

    return () => {
      clearTimeout(timeoutId);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen, onClose]);

  // Handle escape key to close
  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSelect = (id: string) => {
    onSelect(id);
    onClose();
  };

  return (
    <div className="conversation-popover" ref={popoverRef}>
      <div className="conversation-popover-header">
        <span>对话列表</span>
        <button className="popover-close-btn" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="conversation-popover-list">
        {isLoading ? (
          <div className="conversation-popover-empty">加载中...</div>
        ) : error ? (
          <div className="conversation-popover-error">{error}</div>
        ) : conversations.length === 0 ? (
          <div className="conversation-popover-empty">暂无对话</div>
        ) : (
          conversations.map((conversation) => (
            <ConversationItem
              key={conversation.id}
              conversation={conversation}
              isSelected={selectedId === conversation.id}
              collapsed={false}
              onSelect={() => handleSelect(conversation.id)}
              onUpdate={(title) => onUpdate(conversation.id, title)}
              onDelete={() => onDelete(conversation.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}
