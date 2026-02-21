/**
 * Single conversation item in the sidebar list
 */

import { useState, useRef, useEffect } from "react";
import { MessageSquare, Trash2, Check, X, Pencil, FolderPlus, Loader2, MoreVertical } from "lucide-react";
import type { ConversationSummary } from "../../api/conversations";
import type { ProjectSummary } from "../../api/projects";
import "./Conversations.css";

interface ConversationItemProps {
  conversation: ConversationSummary;
  isSelected: boolean;
  collapsed: boolean;
  onSelect: () => void;
  onUpdate: (title: string) => Promise<void>;
  onDelete: () => void;
  // Project association
  projects?: ProjectSummary[];
  onAddToProject?: (conversationId: string, projectId: string) => Promise<void>;
}

export function ConversationItem({
  conversation,
  isSelected,
  collapsed,
  onSelect,
  onUpdate,
  onDelete,
  projects = [],
  onAddToProject,
}: ConversationItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(conversation.title);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [showProjectSubmenu, setShowProjectSubmenu] = useState(false);
  const [addingToProject, setAddingToProject] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
        setShowProjectSubmenu(false);
      }
    };
    if (showMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showMenu]);

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

  const handleMenuClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMenu(!showMenu);
    setShowProjectSubmenu(false);
  };

  const handleRename = () => {
    setEditTitle(conversation.title);
    setIsEditing(true);
    setShowMenu(false);
  };

  const handleDelete = () => {
    setShowMenu(false);
    setShowDeleteConfirm(true);
  };

  const handleAddToProjectHover = () => {
    setShowProjectSubmenu(true);
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

  const handleSelectProject = async (e: React.MouseEvent, projectId: string) => {
    e.stopPropagation();
    if (!onAddToProject) return;

    setAddingToProject(projectId);
    try {
      await onAddToProject(conversation.id, projectId);
      setShowMenu(false);
      setShowProjectSubmenu(false);
    } catch (err) {
      console.error('Failed to add to project:', err);
    } finally {
      setAddingToProject(null);
    }
  };

  if (collapsed) {
    return (
      <button
        className={`conversation-item collapsed ${isSelected ? "selected" : ""}`}
        onClick={onSelect}
        title={conversation.title}
      >
        <MessageSquare size={14} />
      </button>
    );
  }

  return (
    <div
      className={`conversation-item ${isSelected ? "selected" : ""}`}
      onClick={onSelect}
      onDoubleClick={handleDoubleClick}
    >
      <MessageSquare size={14} className="conversation-icon" />

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
          <span className="conversation-title" title={conversation.title}>
            {conversation.title}
          </span>

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
            <div className="conversation-menu-wrapper" ref={menuRef}>
              <button className="conversation-menu-btn" onClick={handleMenuClick}>
                <MoreVertical size={14} />
              </button>

              {showMenu && (
                <div className="conversation-menu">
                  {projects.length > 0 && onAddToProject && (
                    <div
                      className="conversation-menu-item-with-submenu"
                      onMouseEnter={handleAddToProjectHover}
                    >
                      <button>
                        <FolderPlus size={14} />
                        添加到项目
                      </button>
                      {showProjectSubmenu && (
                        <div className="conversation-project-submenu">
                          {projects.map((project) => (
                            <button
                              key={project.id}
                              className="conversation-project-submenu-item"
                              onClick={(e) => handleSelectProject(e, project.id)}
                              disabled={addingToProject !== null}
                            >
                              <span>{project.name}</span>
                              {addingToProject === project.id && <Loader2 size={12} className="spin" />}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  <button onClick={handleRename}>
                    <Pencil size={14} />
                    重命名
                  </button>
                  <button className="danger" onClick={handleDelete}>
                    <Trash2 size={14} />
                    删除对话
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
