/**
 * Floating popover for project list when sidebar is collapsed
 */

import { useEffect, useRef } from "react";
import { X, FolderOpen, Folder, Loader2, FolderPlus } from "lucide-react";
import type { ProjectSummary } from "../../api/projects";
import "./Projects.css";

interface ProjectPopoverProps {
  projects: ProjectSummary[];
  isLoading: boolean;
  error: string | null;
  selectedId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
}

export function ProjectPopover({
  projects,
  isLoading,
  error,
  selectedId,
  isOpen,
  onClose,
  onSelect,
}: ProjectPopoverProps) {
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
    <div className="project-popover" ref={popoverRef}>
      <div className="project-popover-header">
        <span>项目列表</span>
        <button className="popover-close-btn" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="project-popover-list">
        {isLoading ? (
          <div className="project-popover-empty">
            <Loader2 size={16} className="spin" />
            <span>加载中...</span>
          </div>
        ) : error ? (
          <div className="project-popover-error">{error}</div>
        ) : projects.length === 0 ? (
          <div className="project-popover-empty">
            <FolderPlus size={20} />
            <span>暂无项目</span>
          </div>
        ) : (
          projects.map((project) => (
            <div
              key={project.id}
              className={`project-popover-item ${selectedId === project.id ? 'selected' : ''}`}
              onClick={() => handleSelect(project.id)}
            >
              {selectedId === project.id ? (
                <FolderOpen size={16} />
              ) : (
                <Folder size={16} />
              )}
              <span className="project-popover-name" title={project.name}>
                {project.name}
              </span>
              {project.file_count > 0 && (
                <span className="project-popover-count" title={`${project.file_count} 个文件`}>
                  {project.file_count}
                </span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
