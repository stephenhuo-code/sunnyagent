/**
 * Project home page - displayed when a project is selected
 * Shows project header, input for creating new conversations,
 * files/commands cards, and task (conversation) list
 */

import { useState, useCallback } from 'react';
import {
  Folder,
  Plus,
  ArrowUp,
  Loader2,
  MessageSquare,
  FileText,
  Terminal,
} from 'lucide-react';
import type { ProjectDetail, ProjectConversationSummary } from '../../api/projects';
import type { Command, ProjectFile } from '../../types';
import './Projects.css';

interface ProjectHomeProps {
  project: ProjectDetail;
  files: ProjectFile[];
  conversations: ProjectConversationSummary[];
  conversationsLoading: boolean;
  commands: Command[];
  onCreateConversation: (message: string) => Promise<void>;
  onSelectConversation: (conversationId: string) => void;
  onUploadFile: () => void;
}

export function ProjectHome({
  project,
  files,
  conversations,
  conversationsLoading,
  commands,
  onCreateConversation,
  onSelectConversation,
  onUploadFile,
}: ProjectHomeProps) {
  const [inputValue, setInputValue] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = useCallback(async () => {
    if (!inputValue.trim() || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onCreateConversation(inputValue.trim());
      setInputValue('');
    } finally {
      setIsSubmitting(false);
    }
  }, [inputValue, isSubmitting, onCreateConversation]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  const formatRelativeTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins}分钟前`;
    if (diffHours < 24) return `${diffHours}小时前`;
    if (diffDays < 30) return `${diffDays}天前`;
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' });
  };

  return (
    <div className="project-home">
      <div className="project-home-content">
        {/* Project Header */}
        <div className="project-home-header">
          <div className="project-home-icon">
            <Folder size={48} />
          </div>
          <h1 className="project-home-title">{project.name}</h1>
          <p className="project-home-meta">
            由 {project.creator_name} 创建 · {formatDate(project.updated_at)} 更新
          </p>
        </div>

        {/* Input Area */}
        <div className="project-home-input-wrapper">
          <div className="project-home-input">
            <textarea
              placeholder="输入问题开始新的对话"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isSubmitting}
              rows={3}
            />
            <div className="project-home-input-actions">
              <button
                className="action-btn"
                onClick={onUploadFile}
                title="添加文件"
                type="button"
              >
                <Plus size={18} />
              </button>
              <button
                className="action-btn submit"
                onClick={handleSubmit}
                disabled={!inputValue.trim() || isSubmitting}
                title="发送"
                type="button"
              >
                {isSubmitting ? (
                  <Loader2 size={18} className="spin" />
                ) : (
                  <ArrowUp size={18} />
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Cards: Files + Commands */}
        <div className="project-home-cards">
          <FilesCard files={files} onUpload={onUploadFile} />
          <CommandsCard commands={commands} />
        </div>

        {/* Conversations List */}
        <div className="project-home-conversations">
          <h2>会话</h2>
          {conversationsLoading ? (
            <div className="conversations-loading">
              <Loader2 size={20} className="spin" />
            </div>
          ) : conversations.length === 0 ? (
            <div className="conversations-empty">暂无会话</div>
          ) : (
            <div className="conversations-list">
              {conversations.map((conv) => (
                <div
                  key={conv.id}
                  className="conversation-item"
                  onClick={() => onSelectConversation(conv.id)}
                >
                  <MessageSquare size={16} />
                  <span className="conversation-title">{conv.title}</span>
                  <span className="conversation-time">{formatRelativeTime(conv.updated_at)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface FilesCardProps {
  files: ProjectFile[];
  onUpload: () => void;
}

function FilesCard({ files, onUpload }: FilesCardProps) {
  return (
    <div className="project-card">
      <div className="project-card-header">
        <span>文件</span>
        <button onClick={onUpload} type="button">
          <Plus size={16} />
        </button>
      </div>
      <div className="project-card-content">
        {files.length === 0 ? (
          <span className="card-empty">暂无文件</span>
        ) : (
          <>
            <div className="card-file-preview">
              <FileText size={14} />
              <span>{files[0].original_name}</span>
            </div>
            <span className="card-count">{files.length} 个文件</span>
          </>
        )}
      </div>
    </div>
  );
}

interface CommandsCardProps {
  commands: Command[];
}

function CommandsCard({ commands }: CommandsCardProps) {
  return (
    <div className="project-card">
      <div className="project-card-header">
        <span>指令</span>
        <button disabled type="button">
          <Plus size={16} />
        </button>
      </div>
      <div className="project-card-content">
        {commands.length === 0 ? (
          <span className="card-empty">
            <Terminal size={14} /> 没有可用指令
          </span>
        ) : (
          <span className="card-count">{commands.length} 个可用指令</span>
        )}
      </div>
    </div>
  );
}
