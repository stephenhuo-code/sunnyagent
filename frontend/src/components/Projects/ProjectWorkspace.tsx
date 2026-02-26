/**
 * Project workspace with two-column layout (Sources + Chat)
 */

import { useState, useEffect, useCallback } from 'react';
import { SourcesPanel } from './SourcesPanel';
import ChatContainer from '../ChatContainer';
import type { ProjectFile, UploadingProjectFile } from '../../types';
import './Projects.css';

interface ProjectWorkspaceProps {
  projectId: string;
  projectName: string;
  threadId: string | null;
  files: ProjectFile[];
  filesLoading: boolean;
  selectedFileIds: string[];
  uploadingFiles: UploadingProjectFile[];
  onLoadFiles: (projectId: string) => Promise<void>;
  onUploadFile: (projectId: string, file: File) => Promise<void>;
  onDeleteFile: (projectId: string, fileId: string) => Promise<void>;
  onRenameFile: (projectId: string, fileId: string, newName: string) => Promise<void>;
  onToggleFileSelection: (fileId: string) => void;
  onSelectAllFiles: () => void;
  onClearFileSelection: () => void;
  onConversationCreated?: () => void;
  /** Optional initial message to send immediately after component mounts */
  initialMessage?: string | null;
}

export function ProjectWorkspace({
  projectId,
  projectName,
  threadId,
  files,
  filesLoading,
  selectedFileIds,
  uploadingFiles,
  onLoadFiles,
  onUploadFile,
  onDeleteFile,
  onRenameFile,
  onToggleFileSelection,
  onSelectAllFiles,
  onClearFileSelection,
  onConversationCreated,
  initialMessage,
}: ProjectWorkspaceProps) {
  const [sourcesCollapsed, setSourcesCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('sources-panel-collapsed') === 'true';
    }
    return false;
  });

  // Load files when project changes
  useEffect(() => {
    onLoadFiles(projectId);
  }, [projectId, onLoadFiles]);

  // Persist collapsed state
  useEffect(() => {
    localStorage.setItem('sources-panel-collapsed', String(sourcesCollapsed));
  }, [sourcesCollapsed]);

  const toggleCollapse = useCallback(() => {
    setSourcesCollapsed((prev) => !prev);
  }, []);

  return (
    <div className={`project-workspace ${sourcesCollapsed ? 'sources-collapsed' : ''}`}>
      <SourcesPanel
        projectId={projectId}
        files={files}
        filesLoading={filesLoading}
        selectedFileIds={selectedFileIds}
        uploadingFiles={uploadingFiles}
        collapsed={sourcesCollapsed}
        onToggleCollapse={toggleCollapse}
        onUploadFile={onUploadFile}
        onDeleteFile={onDeleteFile}
        onRenameFile={onRenameFile}
        onToggleSelection={onToggleFileSelection}
        onSelectAll={onSelectAllFiles}
        onClearSelection={onClearFileSelection}
      />

      <div className="project-chat">
        <ChatContainer
          key={`project-${projectId}-${threadId || 'new'}`}
          initialThreadId={threadId}
          selectedFileIds={selectedFileIds}
          projectFiles={files}
          onToggleFileSelection={onToggleFileSelection}
          projectContext={{
            projectId,
            projectName,
            selectedFileCount: selectedFileIds.length,
          }}
          onConversationCreated={onConversationCreated}
          initialMessage={initialMessage}
          onUploadToProject={onUploadFile}
        />
      </div>
    </div>
  );
}
