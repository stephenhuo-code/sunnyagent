/**
 * Single conversation item in the sidebar list
 */

import { useState, useRef, useEffect } from "react";
import { MessageSquare, Trash2, Check, X, Pencil } from "lucide-react";
import type { ConversationSummary } from "../../api/conversations";
import "./Conversations.css";

interface ConversationItemProps {
  conversation: ConversationSummary;
  isSelected: boolean;
  collapsed: boolean;
  onSelect: () => void;
  onUpdate: (title: string) => Promise<void>;
  onDelete: () => void;
}

function formatTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));

  if (days === 0) {
    return date.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  } else if (days === 1) {
    return "昨天";
  } else if (days < 7) {
    return date.toLocaleDateString(undefined, { weekday: "short" });
  } else {
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  }
}

export function ConversationItem({
  conversation,
  isSelected,
  collapsed,
  onSelect,
  onUpdate,
  onDelete,
}: ConversationItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(conversation.title);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleDoubleClick = () => {
    if (!collapsed) {
      setEditTitle(conversation.title);
      setIsEditing(true);
    }
  };

  const handleSave = async () => {
    const newTitle = editTitle.trim();
    if (newTitle && newTitle !== conversation.title) {
      await onUpdate(newTitle);
    }
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditTitle(conversation.title);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSave();
    } else if (e.key === "Escape") {
      handleCancel();
    }
  };

  const handleEditClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditTitle(conversation.title);
    setIsEditing(true);
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowDeleteConfirm(true);
  };

  const handleConfirmDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete();
    setShowDeleteConfirm(false);
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowDeleteConfirm(false);
  };

  if (collapsed) {
    return (
      <button
        className={`conversation-item collapsed ${isSelected ? "selected" : ""}`}
        onClick={onSelect}
        title={conversation.title}
      >
        <MessageSquare size={16} />
      </button>
    );
  }

  return (
    <div
      className={`conversation-item ${isSelected ? "selected" : ""}`}
      onClick={onSelect}
      onDoubleClick={handleDoubleClick}
    >
      <MessageSquare size={16} className="conversation-icon" />

      {isEditing ? (
        <div className="conversation-edit" onClick={(e) => e.stopPropagation()}>
          <input
            ref={inputRef}
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={handleSave}
            maxLength={50}
          />
          <button className="edit-action save" onClick={handleSave}>
            <Check size={14} />
          </button>
          <button className="edit-action cancel" onClick={handleCancel}>
            <X size={14} />
          </button>
        </div>
      ) : (
        <>
          <div className="conversation-info">
            <span className="conversation-title" title={conversation.title}>
              {conversation.title}
            </span>
            <span className="conversation-time">
              {formatTime(conversation.updated_at)}
            </span>
          </div>

          {showDeleteConfirm ? (
            <div
              className="delete-confirm"
              onClick={(e) => e.stopPropagation()}
            >
              <button className="confirm-btn yes" onClick={handleConfirmDelete}>
                <Check size={14} />
              </button>
              <button className="confirm-btn no" onClick={handleCancelDelete}>
                <X size={14} />
              </button>
            </div>
          ) : (
            <div className="conversation-actions">
              <button
                className="action-btn edit-btn"
                onClick={handleEditClick}
                title="重命名"
              >
                <Pencil size={14} />
              </button>
              <button
                className="action-btn delete-btn"
                onClick={handleDeleteClick}
                title="删除对话"
              >
                <Trash2 size={14} />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
