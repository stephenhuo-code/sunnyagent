/**
 * Sources panel for managing project files
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import {
  ChevronLeft,
  Plus,
  FileText,
  Trash2,
  Loader2,
  CheckSquare,
  Square,
  FolderClosed,
  MoreVertical,
  Pencil,
} from 'lucide-react';
import type { ProjectFile, UploadingProjectFile } from '../../types';
import './Projects.css';

const ALLOWED_EXTENSIONS = [
  '.pdf', '.docx', '.txt', '.md', '.csv', '.json',
  '.py', '.js', '.ts', '.tsx', '.jsx',
  '.java', '.go', '.c', '.cpp', '.h', '.hpp',
  '.rs', '.rb', '.php', '.swift', '.kt',
];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function truncateFilename(name: string, maxLength: number = 25): string {
  if (name.length <= maxLength) return name;
  const ext = name.includes('.') ? name.slice(name.lastIndexOf('.')) : '';
  const base = name.slice(0, name.length - ext.length);
  const truncatedBase = base.slice(0, maxLength - ext.length - 3);
  return `${truncatedBase}...${ext}`;
}

interface SourcesPanelProps {
  projectId: string;
  files: ProjectFile[];
  filesLoading: boolean;
  selectedFileIds: string[];
  uploadingFiles: UploadingProjectFile[];
  collapsed: boolean;
  onToggleCollapse: () => void;
  onUploadFile: (projectId: string, file: File) => Promise<void>;
  onDeleteFile: (projectId: string, fileId: string) => Promise<void>;
  onRenameFile: (projectId: string, fileId: string, newName: string) => Promise<void>;
  onToggleSelection: (fileId: string) => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
}

export function SourcesPanel({
  projectId,
  files,
  filesLoading,
  selectedFileIds,
  uploadingFiles,
  collapsed,
  onToggleCollapse,
  onUploadFile,
  onDeleteFile,
  onRenameFile,
  onToggleSelection,
  onSelectAll,
  onClearSelection,
}: SourcesPanelProps) {
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [renameError, setRenameError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  const allSelected = files.length > 0 && selectedFileIds.length === files.length;
  const someSelected = selectedFileIds.length > 0 && !allSelected;

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const inputFiles = e.target.files;
    if (!inputFiles) return;

    for (const file of Array.from(inputFiles)) {
      // Validate extension
      const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        alert(`不支持的文件类型: ${ext}`);
        continue;
      }

      // Validate size
      if (file.size > MAX_FILE_SIZE) {
        alert(`文件过大: ${file.name}。最大支持: 10MB`);
        continue;
      }

      await onUploadFile(projectId, file);
    }

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [projectId, onUploadFile]);

  const handleDelete = async (fileId: string) => {
    setMenuOpenId(null);
    if (window.confirm('确定要删除这个文件吗？')) {
      setDeletingIds((prev) => new Set(prev).add(fileId));
      try {
        await onDeleteFile(projectId, fileId);
      } finally {
        setDeletingIds((prev) => {
          const next = new Set(prev);
          next.delete(fileId);
          return next;
        });
      }
    }
  };

  const handleStartRename = (file: ProjectFile) => {
    setMenuOpenId(null);
    setRenamingId(file.file_id);
    setRenameValue(file.original_name);
    setRenameError(null);
  };

  const handleCancelRename = () => {
    setRenamingId(null);
    setRenameValue('');
    setRenameError(null);
  };

  const handleConfirmRename = async () => {
    if (!renamingId || !renameValue.trim()) return;

    const file = files.find((f) => f.file_id === renamingId);
    if (!file) return;

    // No change
    if (renameValue.trim() === file.original_name) {
      handleCancelRename();
      return;
    }

    try {
      await onRenameFile(projectId, renamingId, renameValue.trim());
      handleCancelRename();
    } catch (err) {
      setRenameError(err instanceof Error ? err.message : '重命名失败');
    }
  };

  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleConfirmRename();
    } else if (e.key === 'Escape') {
      handleCancelRename();
    }
  };

  // Focus rename input when entering rename mode
  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      // Select filename without extension
      const dotIndex = renameValue.lastIndexOf('.');
      if (dotIndex > 0) {
        renameInputRef.current.setSelectionRange(0, dotIndex);
      } else {
        renameInputRef.current.select();
      }
    }
  }, [renamingId]);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuOpenId) {
        const target = e.target as Element;
        if (!target.closest('.source-menu-wrapper')) {
          setMenuOpenId(null);
        }
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [menuOpenId]);

  const handleSelectAllClick = () => {
    if (allSelected) {
      onClearSelection();
    } else {
      onSelectAll();
    }
  };

  // Collapsed state
  if (collapsed) {
    return (
      <div className="sources-panel collapsed">
        <button className="sources-expand-btn" onClick={onToggleCollapse} title="展开文件面板">
          <FolderClosed size={20} />
        </button>
      </div>
    );
  }

  return (
    <div className="sources-panel">
      {/* Header */}
      <div className="sources-header">
        <div className="sources-title">
          <span>资料库</span>
          {selectedFileIds.length > 0 && (
            <span className="sources-selected-count">
              已选 {selectedFileIds.length} 个
            </span>
          )}
        </div>
        <button className="sources-collapse-btn" onClick={onToggleCollapse} title="收起面板">
          <ChevronLeft size={18} />
        </button>
      </div>

      {/* Add sources button */}
      <input
        ref={fileInputRef}
        type="file"
        accept={ALLOWED_EXTENSIONS.join(',')}
        multiple
        onChange={handleFileSelect}
        style={{ display: 'none' }}
      />
      <button
        className="sources-add-btn"
        onClick={() => fileInputRef.current?.click()}
      >
        <Plus size={16} />
        <span>添加资料</span>
      </button>

      {/* Select all checkbox */}
      {files.length > 0 && (
        <div className="sources-select-all">
          <button onClick={handleSelectAllClick}>
            <span>全选</span>
            {allSelected ? (
              <CheckSquare size={16} />
            ) : someSelected ? (
              <Square size={16} className="partial" />
            ) : (
              <Square size={16} />
            )}
          </button>
        </div>
      )}

      {/* File list */}
      <div className="sources-list">
        {filesLoading ? (
          <div className="sources-loading">
            <Loader2 size={20} className="spin" />
            <span>加载文件...</span>
          </div>
        ) : files.length === 0 && uploadingFiles.length === 0 ? (
          <div className="sources-empty">
            <FileText size={32} />
            <span>暂无文件</span>
            <span className="sources-empty-hint">点击上方按钮添加文件</span>
          </div>
        ) : (
          <>
            {/* Uploading files */}
            {uploadingFiles.map((item) => (
              <div key={item.id} className={`source-item uploading ${item.status}`}>
                <div className="source-action-placeholder">
                  <Loader2 size={14} className="spin" />
                </div>
                <div className="source-icon">
                  <FileText size={18} />
                </div>
                <div className="source-info">
                  <span className="source-name" title={item.file.name}>
                    {truncateFilename(item.file.name)}
                  </span>
                  <span className="source-meta">
                    {item.status === 'uploading' ? `上传中 ${item.progress}%` : item.error || '完成'}
                  </span>
                </div>
                {item.status === 'uploading' && (
                  <div className="source-progress" style={{ width: `${item.progress}%` }} />
                )}
              </div>
            ))}

            {/* Existing files */}
            {files.map((file) => {
              const isSelected = selectedFileIds.includes(file.file_id);
              const isDeleting = deletingIds.has(file.file_id);
              const isRenaming = renamingId === file.file_id;

              return (
                <div
                  key={file.file_id}
                  className={`source-item ${isSelected ? 'selected' : ''} ${isDeleting ? 'deleting' : ''}`}
                  onClick={() => !isRenaming && onToggleSelection(file.file_id)}
                >
                  <div className="source-menu-wrapper">
                    <button
                      className="source-more-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuOpenId(menuOpenId === file.file_id ? null : file.file_id);
                      }}
                      disabled={isDeleting || isRenaming}
                      title="更多选项"
                    >
                      {isDeleting ? <Loader2 size={14} className="spin" /> : <MoreVertical size={14} />}
                    </button>
                    {menuOpenId === file.file_id && (
                      <div className="source-menu">
                        <button onClick={() => handleStartRename(file)}>
                          <Pencil size={14} />
                          <span>重命名</span>
                        </button>
                        <button className="danger" onClick={() => handleDelete(file.file_id)}>
                          <Trash2 size={14} />
                          <span>删除</span>
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="source-icon">
                    <FileText size={18} />
                  </div>
                  <div className="source-info">
                    {isRenaming ? (
                      <div className="source-rename-container" onClick={(e) => e.stopPropagation()}>
                        <input
                          ref={renameInputRef}
                          type="text"
                          className="source-rename-input"
                          value={renameValue}
                          onChange={(e) => {
                            setRenameValue(e.target.value);
                            setRenameError(null);
                          }}
                          onKeyDown={handleRenameKeyDown}
                          onBlur={handleConfirmRename}
                        />
                        {renameError && <span className="source-rename-error">{renameError}</span>}
                      </div>
                    ) : (
                      <>
                        <span className="source-name" title={file.original_name}>
                          {truncateFilename(file.original_name)}
                        </span>
                        <span className="source-meta">
                          {formatSize(file.size_bytes)}
                        </span>
                      </>
                    )}
                  </div>
                  <div className="source-checkbox">
                    {isSelected ? <CheckSquare size={16} /> : <Square size={16} />}
                  </div>
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}
