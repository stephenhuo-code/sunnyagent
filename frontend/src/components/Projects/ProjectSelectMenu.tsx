/**
 * Dropdown menu for selecting a project to add a conversation to
 */

import { useState, useRef, useEffect } from 'react';
import { FolderPlus, Check, Loader2 } from 'lucide-react';
import type { ProjectSummary } from '../../api/projects';
import './Projects.css';

interface ProjectSelectMenuProps {
  projects: ProjectSummary[];
  isLoading: boolean;
  currentProjectId?: string | null;
  onSelect: (projectId: string) => Promise<void>;
  onClose: () => void;
}

export function ProjectSelectMenu({
  projects,
  isLoading,
  currentProjectId,
  onSelect,
  onClose,
}: ProjectSelectMenuProps) {
  const [selecting, setSelecting] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  const handleSelect = async (projectId: string) => {
    if (projectId === currentProjectId) {
      onClose();
      return;
    }

    setSelecting(projectId);
    try {
      await onSelect(projectId);
      onClose();
    } catch (err) {
      console.error('Failed to add to project:', err);
    } finally {
      setSelecting(null);
    }
  };

  return (
    <div className="project-select-menu" ref={menuRef}>
      <div className="project-select-header">
        <FolderPlus size={14} />
        <span>添加到项目</span>
      </div>

      {isLoading ? (
        <div className="project-select-loading">
          <Loader2 size={14} className="spin" />
          <span>加载中...</span>
        </div>
      ) : projects.length === 0 ? (
        <div className="project-select-empty">
          暂无项目
        </div>
      ) : (
        <div className="project-select-list">
          {projects.map((project) => (
            <button
              key={project.id}
              className={`project-select-item ${project.id === currentProjectId ? 'current' : ''}`}
              onClick={() => handleSelect(project.id)}
              disabled={selecting !== null}
            >
              <span className="project-select-name">{project.name}</span>
              {project.id === currentProjectId && <Check size={14} />}
              {selecting === project.id && <Loader2 size={14} className="spin" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
