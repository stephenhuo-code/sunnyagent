/**
 * List of conversations in the sidebar
 */

import { MessageSquare, Loader2 } from "lucide-react";
import { ConversationItem } from "./ConversationItem";
import type { ConversationSummary } from "../../api/conversations";
import "./Conversations.css";

interface ConversationListProps {
  conversations: ConversationSummary[];
  isLoading: boolean;
  error: string | null;
  selectedId: string | null;
  collapsed: boolean;
  onSelect: (id: string, threadId?: string) => void;
  onUpdate: (id: string, title: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

export function ConversationList({
  conversations,
  isLoading,
  error,
  selectedId,
  collapsed,
  onSelect,
  onUpdate,
  onDelete,
}: ConversationListProps) {
  if (isLoading) {
    return (
      <div className="conversation-loading">
        <Loader2 size={20} className="spin" />
        {!collapsed && <span>加载中...</span>}
      </div>
    );
  }

  if (error) {
    return (
      <div className="conversation-error">
        {!collapsed && <span>{error}</span>}
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <div className="conversation-empty">
        <MessageSquare size={24} className="empty-icon" />
        {!collapsed && (
          <span className="empty-text">
            暂无对话，点击"新建对话"开始
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="conversation-list">
      {conversations.map((conversation) => (
        <ConversationItem
          key={conversation.id}
          conversation={conversation}
          isSelected={selectedId === conversation.id}
          collapsed={collapsed}
          onSelect={() => onSelect(conversation.id)}
          onUpdate={(title) => onUpdate(conversation.id, title)}
          onDelete={() => onDelete(conversation.id)}
        />
      ))}
    </div>
  );
}
