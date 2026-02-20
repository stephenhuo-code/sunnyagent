/**
 * Main sidebar component with navigation
 */

import { useState, useEffect, useRef, ReactNode } from 'react';
import { MessagesSquare, MessageSquarePlus, Settings, LogOut, User, FolderKanban, FolderPlus } from 'lucide-react';
import { SidebarHeader } from './SidebarHeader';
import { useAuth } from '../../hooks/useAuth';
import { ConversationPopover } from '../Conversations/ConversationPopover';
import { ProjectPopover } from '../Projects/ProjectPopover';
import type { ConversationSummary } from '../../api/conversations';
import type { ProjectSummary } from '../../api/projects';
import './Layout.css';

interface SidebarProps {
  onNewConversation: () => void;
  onAdminClick?: () => void;
  children?: ReactNode | ((collapsed: boolean) => ReactNode);
  // Props for popover when collapsed
  conversations?: ConversationSummary[];
  conversationsLoading?: boolean;
  conversationsError?: string | null;
  selectedConversationId?: string | null;
  onSelectConversation?: (id: string) => void;
  onUpdateConversation?: (id: string, title: string) => Promise<void>;
  onDeleteConversation?: (id: string) => Promise<void>;
  // Projects section
  projectsSection?: ReactNode | ((collapsed: boolean) => ReactNode);
  onCreateProject?: () => void;
  // Props for project popover when collapsed
  projects?: ProjectSummary[];
  projectsLoading?: boolean;
  projectsError?: string | null;
  selectedProjectId?: string | null;
  onSelectProject?: (id: string) => void;
}

export function Sidebar({
  onNewConversation,
  onAdminClick,
  children,
  conversations = [],
  conversationsLoading = false,
  conversationsError = null,
  selectedConversationId = null,
  onSelectConversation,
  onUpdateConversation,
  onDeleteConversation,
  projectsSection,
  onCreateProject,
  projects = [],
  projectsLoading = false,
  projectsError = null,
  selectedProjectId = null,
  onSelectProject,
}: SidebarProps) {
  const { user, isAdmin, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(() => {
    const saved = localStorage.getItem('sidebar-collapsed');
    return saved === 'true';
  });
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [projectPopoverOpen, setProjectPopoverOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem('sidebar-collapsed', String(collapsed));
  }, [collapsed]);

  // Close popovers when expanding sidebar
  useEffect(() => {
    if (!collapsed) {
      setPopoverOpen(false);
      setProjectPopoverOpen(false);
    }
  }, [collapsed]);

  // Close user menu when clicking outside or pressing Escape
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setUserMenuOpen(false);
      }
    };

    if (userMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [userMenuOpen]);

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const handlePopoverSelect = (id: string) => {
    onSelectConversation?.(id);
  };

  const handleProjectPopoverSelect = (id: string) => {
    onSelectProject?.(id);
  };

  const handlePopoverUpdate = async (id: string, title: string) => {
    await onUpdateConversation?.(id, title);
  };

  const handlePopoverDelete = async (id: string) => {
    await onDeleteConversation?.(id);
  };

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <SidebarHeader collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />

      <div className="sidebar-content">
        {/* Projects Section */}
        {projectsSection && (
          <div className="sidebar-section">
            {collapsed ? (
              <button
                className="sidebar-btn project-popover-trigger"
                onClick={() => setProjectPopoverOpen(true)}
                title="项目"
              >
                <FolderKanban size={20} />
              </button>
            ) : (
              <>
                <div className="sidebar-section-header">
                  <FolderKanban size={18} />
                  <span>项目</span>
                  {onCreateProject && (
                    <button
                      className="section-action-btn"
                      onClick={onCreateProject}
                      title="新建项目"
                    >
                      <FolderPlus size={16} />
                    </button>
                  )}
                </div>
                <div className="sidebar-section-content">
                  {typeof projectsSection === 'function' ? projectsSection(collapsed) : projectsSection}
                </div>
              </>
            )}
          </div>
        )}

        {/* Conversations Section */}
        <div className="sidebar-section">
          {collapsed ? (
            /* Collapsed: Section header becomes clickable popover trigger */
            <button
              className="sidebar-btn conversation-popover-trigger"
              onClick={() => setPopoverOpen(true)}
              title="对话"
            >
              <MessagesSquare size={20} />
            </button>
          ) : (
            /* Expanded: Show header and full conversation list */
            <>
              <div className="sidebar-section-header">
                <MessagesSquare size={18} />
                <span>对话</span>
                <button
                  className="section-action-btn"
                  onClick={onNewConversation}
                  title="新建对话"
                >
                  <MessageSquarePlus size={16} />
                </button>
              </div>
              <div className="sidebar-section-content">
                {typeof children === 'function' ? children(collapsed) : children}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Conversation Popover for collapsed mode */}
      {collapsed && (
        <ConversationPopover
          conversations={conversations}
          isLoading={conversationsLoading}
          error={conversationsError}
          selectedId={selectedConversationId}
          isOpen={popoverOpen}
          onClose={() => setPopoverOpen(false)}
          onSelect={handlePopoverSelect}
          onUpdate={handlePopoverUpdate}
          onDelete={handlePopoverDelete}
        />
      )}

      {/* Project Popover for collapsed mode */}
      {collapsed && (
        <ProjectPopover
          projects={projects}
          isLoading={projectsLoading}
          error={projectsError}
          selectedId={selectedProjectId}
          isOpen={projectPopoverOpen}
          onClose={() => setProjectPopoverOpen(false)}
          onSelect={handleProjectPopoverSelect}
        />
      )}

      {/* Bottom Navigation - Icon Row */}
      <div className="sidebar-footer">
        {isAdmin && !collapsed && (
          <button
            className="sidebar-footer-icon"
            onClick={onAdminClick}
            title="系统管理"
          >
            <Settings size={20} />
          </button>
        )}

        {/* User Menu */}
        <div className="user-menu-container" ref={userMenuRef}>
          <button
            className="sidebar-footer-icon"
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            title="用户菜单"
          >
            <User size={20} />
          </button>

          {userMenuOpen && (
            <div className="user-menu-popover">
              <div className="user-menu-info">
                <div className="user-menu-item">
                  <span className="user-menu-label">用户类型</span>
                  <span className="user-menu-value">{user?.role === 'admin' ? '管理员' : '用户'}</span>
                </div>
                <div className="user-menu-item">
                  <span className="user-menu-label">用户名</span>
                  <span className="user-menu-value">{user?.username}</span>
                </div>
              </div>
              <button className="user-menu-logout" onClick={handleLogout}>
                <LogOut size={16} />
                <span>退出登录</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
