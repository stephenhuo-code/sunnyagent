/**
 * Single project item in the sidebar with expandable conversations
 */

import { useState, useRef, useEffect } from 'react';
import { FolderOpen, Folder, ChevronRight, ChevronDown, MoreVertical, MessageSquare, Loader2 } from 'lucide-react';
import type { ProjectSummary, ProjectConversationSummary } from '../../api/projects';
import './Projects.css';

interface ProjectItemProps {
  project: ProjectSummary;
  isSelected: boolean;
  isExpanded: boolean;
  conversations: ProjectConversationSummary[];
  conversationsLoading: boolean;
  collapsed?: boolean;
  selectedConversationId?: string | null;
  onSelect: (id: string) => void;
  onExpand: (id: string) => void;
  onRename: (id: string, name: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onSelectConversation: (conversationId: string, projectId: string) => void;
  onRemoveConversation: (conversationId: string, projectId: string) => void;
}

export function ProjectItem({
  project,
  isSelected,
  isExpanded,
  conversations,
  conversationsLoading,
  collapsed = false,
  selectedConversationId,
  onSelect,
  onExpand,
  onRename,
  onDelete,
  onSelectConversation,
  onRemoveConversation,
}: ProjectItemProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [showConvMenu, setShowConvMenu] = useState<string | null>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [newName, setNewName] = useState(project.name);
  const menuRef = useRef<HTMLDivElement>(null);
  const convMenuRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
      if (convMenuRef.current && !convMenuRef.current.contains(e.target as Node)) {
        setShowConvMenu(null);
      }
    };
    if (showMenu || showConvMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showMenu, showConvMenu]);

  useEffect(() => {
    if (isRenaming) {
      inputRef.current?.select();
    }
  }, [isRenaming]);

  const handleToggleExpand = (e: React.MouseEvent) => {
    e.stopPropagation();
    onExpand(project.id);
  };

  const handleClick = () => {
    onSelect(project.id);
  };

  const handleMenuClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMenu(!showMenu);
  };

  const handleRename = () => {
    setIsRenaming(true);
    setShowMenu(false);
  };

  const handleRenameSubmit = async () => {
    const trimmed = newName.trim();
    if (trimmed && trimmed !== project.name) {
      try {
        await onRename(project.id, trimmed);
      } catch (err) {
        setNewName(project.name);
      }
    } else {
      setNewName(project.name);
    }
    setIsRenaming(false);
  };

  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleRenameSubmit();
    } else if (e.key === 'Escape') {
      setNewName(project.name);
      setIsRenaming(false);
    }
  };

  const handleDelete = async () => {
    setShowMenu(false);
    if (window.confirm(`确定要删除项目 "${project.name}" 吗？\n项目中的文件将被删除，对话将移至历史记录。`)) {
      await onDelete(project.id);
    }
  };

  const handleConvMenuClick = (e: React.MouseEvent, conversationId: string) => {
    e.stopPropagation();
    setShowConvMenu(showConvMenu === conversationId ? null : conversationId);
  };

  const handleRemoveConversation = (conversationId: string) => {
    setShowConvMenu(null);
    onRemoveConversation(conversationId, project.id);
  };

  // If a conversation in this project is selected, don't highlight the project itself
  const hasSelectedConversation = selectedConversationId && conversations.some(c => c.id === selectedConversationId);
  const showProjectSelected = isSelected && !hasSelectedConversation;
  // Show folder open icon if:
  // 1. This project has the selected conversation, OR
  // 2. This project is selected AND there's no conversation selected globally
  const showFolderOpen = hasSelectedConversation || (isSelected && !selectedConversationId);

  if (collapsed) {
    return (
      <div
        className={`project-item collapsed ${showProjectSelected ? 'selected' : ''}`}
        onClick={handleClick}
        title={project.name}
      >
        {showFolderOpen ? <FolderOpen size={18} /> : <Folder size={18} />}
      </div>
    );
  }

  return (
    <div className={`project-item-wrapper ${isExpanded ? 'expanded' : ''}`}>
      <div
        className={`project-item ${showProjectSelected ? 'selected' : ''}`}
        onClick={handleClick}
      >
        <button className="expand-btn" onClick={handleToggleExpand}>
          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>

        {showFolderOpen ? <FolderOpen size={16} /> : <Folder size={16} />}

        {isRenaming ? (
          <input
            ref={inputRef}
            className="project-rename-input"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onBlur={handleRenameSubmit}
            onKeyDown={handleRenameKeyDown}
            onClick={(e) => e.stopPropagation()}
            maxLength={100}
          />
        ) : (
          <span className="project-name" title={project.name}>
            {project.name}
          </span>
        )}

        <div className="project-meta">
          {project.file_count > 0 && (
            <span className="project-count" title={`${project.file_count} 个文件`}>
              {project.file_count}
            </span>
          )}
        </div>

        <div className="project-menu-wrapper" ref={menuRef}>
          <button className="project-menu-btn" onClick={handleMenuClick}>
            <MoreVertical size={14} />
          </button>

          {showMenu && (
            <div className="project-menu">
              <button onClick={handleRename}>重命名</button>
              <button className="danger" onClick={handleDelete}>删除项目</button>
            </div>
          )}
        </div>
      </div>

      {/* Conversations under project */}
      {isExpanded && (
        <div className="project-conversations">
          {conversationsLoading ? (
            <div className="project-conversations-loading">
              <Loader2 size={14} className="spin" />
              <span>加载中...</span>
            </div>
          ) : conversations.length === 0 ? (
            <div className="project-conversations-empty">
              暂无对话
            </div>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                className={`project-conversation-item ${conv.id === selectedConversationId ? 'selected' : ''}`}
                onClick={() => onSelectConversation(conv.id, project.id)}
              >
                <MessageSquare size={14} />
                <span className="conversation-title" title={conv.title}>
                  {conv.title}
                </span>

                <div className="conversation-menu-wrapper" ref={showConvMenu === conv.id ? convMenuRef : undefined}>
                  <button
                    className="conversation-menu-btn"
                    onClick={(e) => handleConvMenuClick(e, conv.id)}
                  >
                    <MoreVertical size={12} />
                  </button>

                  {showConvMenu === conv.id && (
                    <div className="conversation-menu">
                      <button onClick={() => handleRemoveConversation(conv.id)}>
                        从项目移除
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
