/**
 * Main sidebar component with navigation
 */

import { useState, useEffect, ReactNode } from 'react';
import { Plus, MessagesSquare, Settings, LogOut, User } from 'lucide-react';
import { SidebarHeader } from './SidebarHeader';
import { useAuth } from '../../hooks/useAuth';
import { ConversationPopover } from '../Conversations/ConversationPopover';
import type { ConversationSummary } from '../../api/conversations';
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
}: SidebarProps) {
  const { user, isAdmin, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(() => {
    const saved = localStorage.getItem('sidebar-collapsed');
    return saved === 'true';
  });
  const [popoverOpen, setPopoverOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem('sidebar-collapsed', String(collapsed));
  }, [collapsed]);

  // Close popover when expanding sidebar
  useEffect(() => {
    if (!collapsed) {
      setPopoverOpen(false);
    }
  }, [collapsed]);

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
        {/* New Conversation Button */}
        <button className="sidebar-btn primary" onClick={onNewConversation}>
          <Plus size={20} />
          {!collapsed && <span>新建对话</span>}
        </button>

        {/* Conversations Section */}
        <div className="sidebar-section">
          {collapsed ? (
            /* Collapsed: Section header becomes clickable popover trigger */
            <button
              className="sidebar-btn conversation-popover-trigger"
              onClick={() => setPopoverOpen(true)}
              title="查看对话列表"
            >
              <MessagesSquare size={20} />
            </button>
          ) : (
            /* Expanded: Show header and full conversation list */
            <>
              <div className="sidebar-section-header">
                <MessagesSquare size={18} />
                <span>对话列表</span>
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

      {/* Bottom Navigation */}
      <div className="sidebar-footer">
        {/* Admin Section - Only visible to admins */}
        {isAdmin && (
          <button className="sidebar-btn" onClick={onAdminClick}>
            <Settings size={20} />
            {!collapsed && <span>系统管理</span>}
          </button>
        )}

        {/* User Info & Logout */}
        <div className="sidebar-user">
          <div className="user-info">
            <User size={20} />
            {!collapsed && (
              <div className="user-details">
                <span className="user-name">{user?.username}</span>
                <span className="user-role">{user?.role === 'admin' ? '管理员' : '用户'}</span>
              </div>
            )}
          </div>
          <button className="sidebar-btn logout" onClick={handleLogout} title="退出登录">
            <LogOut size={20} />
            {!collapsed && <span>退出登录</span>}
          </button>
        </div>
      </div>
    </aside>
  );
}
