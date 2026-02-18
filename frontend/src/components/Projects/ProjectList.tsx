/**
 * Project list component with expandable tree structure
 */

import { useState, useCallback, useEffect } from 'react';
import { Plus, FolderPlus, Loader2 } from 'lucide-react';
import { ProjectItem } from './ProjectItem';
import { NewProjectModal } from './NewProjectModal';
import type { ProjectSummary, ProjectConversationSummary } from '../../api/projects';
import './Projects.css';

interface ProjectListProps {
  projects: ProjectSummary[];
  isLoading: boolean;
  error: string | null;
  selectedProjectId: string | null;
  collapsed?: boolean;
  selectedConversationId?: string | null;
  onSelectProject: (id: string) => void;
  onCreateProject: (name: string) => Promise<void>;
  onRenameProject: (id: string, name: string) => Promise<void>;
  onDeleteProject: (id: string) => Promise<void>;
  // Conversations (per-project caching)
  getProjectConversations: (projectId: string) => ProjectConversationSummary[];
  isConversationsLoading: (projectId: string) => boolean;
  onLoadConversations: (projectId: string) => Promise<void>;
  onSelectConversation: (conversationId: string, projectId: string) => void;
  onRemoveConversation: (conversationId: string, projectId: string) => Promise<void>;
}

export function ProjectList({
  projects,
  isLoading,
  error,
  selectedProjectId,
  collapsed = false,
  selectedConversationId,
  onSelectProject,
  onCreateProject,
  onRenameProject,
  onDeleteProject,
  getProjectConversations,
  isConversationsLoading,
  onLoadConversations,
  onSelectConversation,
  onRemoveConversation,
}: ProjectListProps) {
  const [showNewModal, setShowNewModal] = useState(false);
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set());
  const [loadedProjects, setLoadedProjects] = useState<Set<string>>(new Set());

  const handleExpand = useCallback(async (projectId: string) => {
    setExpandedProjects((prev) => {
      const next = new Set(prev);
      if (next.has(projectId)) {
        next.delete(projectId);
      } else {
        next.add(projectId);
        // Load conversations when expanding
        if (!loadedProjects.has(projectId)) {
          onLoadConversations(projectId);
          setLoadedProjects((prev) => new Set(prev).add(projectId));
        }
      }
      return next;
    });
  }, [loadedProjects, onLoadConversations]);

  // Auto-expand and load when project is selected
  useEffect(() => {
    if (selectedProjectId && !expandedProjects.has(selectedProjectId)) {
      handleExpand(selectedProjectId);
    }
  }, [selectedProjectId]);

  const handleCreate = async (name: string) => {
    await onCreateProject(name);
  };

  if (collapsed) {
    return (
      <div className="project-list collapsed">
        <button
          className="project-add-btn"
          onClick={() => setShowNewModal(true)}
          title="新建项目"
        >
          <FolderPlus size={18} />
        </button>

        {isLoading ? (
          <div className="project-loading">
            <Loader2 size={16} className="spin" />
          </div>
        ) : (
          projects.map((project) => (
            <ProjectItem
              key={project.id}
              project={project}
              isSelected={project.id === selectedProjectId}
              isExpanded={false}
              conversations={[]}
              conversationsLoading={false}
              collapsed={true}
              selectedConversationId={selectedConversationId}
              onSelect={onSelectProject}
              onExpand={() => {}}
              onRename={onRenameProject}
              onDelete={onDeleteProject}
              onSelectConversation={onSelectConversation}
              onRemoveConversation={onRemoveConversation}
            />
          ))
        )}

        <NewProjectModal
          isOpen={showNewModal}
          onClose={() => setShowNewModal(false)}
          onCreate={handleCreate}
        />
      </div>
    );
  }

  return (
    <div className="project-list">
      <div className="project-list-header">
        <span>项目</span>
        <button
          className="project-add-btn"
          onClick={() => setShowNewModal(true)}
          title="新建项目"
        >
          <Plus size={16} />
        </button>
      </div>

      {isLoading ? (
        <div className="project-loading">
          <Loader2 size={20} className="spin" />
          <span>加载中...</span>
        </div>
      ) : error ? (
        <div className="project-error">{error}</div>
      ) : projects.length === 0 ? (
        <div className="project-empty">
          <FolderPlus size={24} />
          <span>暂无项目</span>
          <button className="btn-link" onClick={() => setShowNewModal(true)}>
            创建第一个项目
          </button>
        </div>
      ) : (
        <div className="project-items">
          {projects.map((project) => (
            <ProjectItem
              key={project.id}
              project={project}
              isSelected={project.id === selectedProjectId}
              isExpanded={expandedProjects.has(project.id)}
              conversations={getProjectConversations(project.id)}
              conversationsLoading={isConversationsLoading(project.id)}
              selectedConversationId={selectedConversationId}
              onSelect={onSelectProject}
              onExpand={handleExpand}
              onRename={onRenameProject}
              onDelete={onDeleteProject}
              onSelectConversation={onSelectConversation}
              onRemoveConversation={onRemoveConversation}
            />
          ))}
        </div>
      )}

      <NewProjectModal
        isOpen={showNewModal}
        onClose={() => setShowNewModal(false)}
        onCreate={handleCreate}
      />
    </div>
  );
}
