/**
 * Hook for managing project list state
 */

import { useState, useEffect, useCallback, useRef } from "react";
import {
  listProjects,
  createProject,
  updateProject,
  deleteProject,
  listProjectFiles,
  uploadProjectFile,
  deleteProjectFile,
  renameProjectFile,
  listProjectConversations,
  addConversationToProject,
  removeConversationFromProject,
  type ProjectSummary,
  type ProjectDetail,
  type ProjectConversationSummary,
} from "../api/projects";
import type { ProjectFile, UploadingProjectFile } from "../types";

export interface UseProjectsResult {
  // Project list state
  projects: ProjectSummary[];
  isLoading: boolean;
  error: string | null;
  selectedProjectId: string | null;

  // Project CRUD
  refresh: () => Promise<void>;
  create: (name: string) => Promise<ProjectDetail>;
  update: (id: string, name: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
  select: (id: string | null) => void;

  // Current project files
  files: ProjectFile[];
  filesLoading: boolean;
  selectedFileIds: string[];
  loadFiles: (projectId: string) => Promise<void>;
  uploadFile: (projectId: string, file: File) => Promise<void>;
  removeFile: (projectId: string, fileId: string) => Promise<void>;
  renameFile: (projectId: string, fileId: string, newName: string) => Promise<void>;
  toggleFileSelection: (fileId: string) => void;
  selectAllFiles: () => void;
  clearFileSelection: () => void;
  uploadingFiles: UploadingProjectFile[];

  // Project conversations (per-project caching)
  getConversations: (projectId: string) => ProjectConversationSummary[];
  isConversationsLoading: (projectId: string) => boolean;
  loadConversations: (projectId: string) => Promise<void>;
  addConversation: (conversationId: string, projectId: string) => Promise<void>;
  removeConversation: (conversationId: string, projectId?: string) => Promise<void>;
}

const PROJECT_STORAGE_KEY = "selected-project-id";

export function useProjects(): UseProjectsResult {
  // Project list state
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem(PROJECT_STORAGE_KEY);
    }
    return null;
  });

  // Current project files
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState<UploadingProjectFile[]>([]);

  // Per-project conversations cache
  const [conversationsCache, setConversationsCache] = useState<Map<string, ProjectConversationSummary[]>>(new Map());
  const [loadingProjects, setLoadingProjects] = useState<Set<string>>(new Set());

  // Track previous project ID to clear files when switching
  const prevProjectIdRef = useRef<string | null>(selectedProjectId);

  // ==========================================================================
  // Project List Operations
  // ==========================================================================

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await listProjects();
      setProjects(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载项目列表失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const create = useCallback(async (name: string): Promise<ProjectDetail> => {
    const project = await createProject(name);
    setProjects((prev) => [
      {
        id: project.id,
        name: project.name,
        creator_name: project.creator_name,
        file_count: project.file_count,
        conversation_count: project.conversation_count,
        created_at: project.created_at,
        updated_at: project.updated_at,
      },
      ...prev,
    ]);
    setSelectedProjectId(project.id);
    localStorage.setItem(PROJECT_STORAGE_KEY, project.id);
    return project;
  }, []);

  const update = useCallback(async (id: string, name: string) => {
    await updateProject(id, name);
    setProjects((prev) =>
      prev.map((p) => (p.id === id ? { ...p, name } : p))
    );
  }, []);

  const remove = useCallback(async (id: string) => {
    await deleteProject(id);
    setProjects((prev) => prev.filter((p) => p.id !== id));
    if (selectedProjectId === id) {
      setSelectedProjectId(null);
      localStorage.removeItem(PROJECT_STORAGE_KEY);
      setFiles([]);
      setSelectedFileIds([]);
    }
    // Remove from conversations cache
    setConversationsCache((prev) => {
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
  }, [selectedProjectId]);

  // Clear files when switching to a different project
  useEffect(() => {
    if (selectedProjectId !== prevProjectIdRef.current) {
      setFiles([]);
      setSelectedFileIds([]);
      prevProjectIdRef.current = selectedProjectId;
    }
  }, [selectedProjectId]);

  const select = useCallback((id: string | null) => {
    setSelectedProjectId(id);
    if (id) {
      localStorage.setItem(PROJECT_STORAGE_KEY, id);
    } else {
      localStorage.removeItem(PROJECT_STORAGE_KEY);
    }
  }, []);

  // ==========================================================================
  // File Operations
  // ==========================================================================

  const loadFiles = useCallback(async (projectId: string) => {
    setFilesLoading(true);
    try {
      const result = await listProjectFiles(projectId);
      setFiles(result.map((f) => ({ ...f, selected: false })));
      setSelectedFileIds([]);
    } catch (err) {
      console.error("Failed to load files:", err);
    } finally {
      setFilesLoading(false);
    }
  }, []);

  const uploadFileToProject = useCallback(async (projectId: string, file: File) => {
    const uploadId = `upload-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const uploadingFile: UploadingProjectFile = {
      id: uploadId,
      file,
      progress: 0,
      status: "uploading",
    };

    setUploadingFiles((prev) => [...prev, uploadingFile]);

    try {
      const uploaded = await uploadProjectFile(projectId, file, (progress) => {
        setUploadingFiles((prev) =>
          prev.map((f) => (f.id === uploadId ? { ...f, progress } : f))
        );
      });

      // Convert to ProjectFile format
      const projectFile: ProjectFile = {
        id: uploaded.id,
        file_id: uploaded.file_id,
        original_name: uploaded.original_name,
        content_type: uploaded.content_type,
        size_bytes: uploaded.size_bytes,
        created_at: new Date().toISOString(),
        download_url: uploaded.download_url,
        selected: false,
      };

      setUploadingFiles((prev) =>
        prev.map((f) =>
          f.id === uploadId
            ? { ...f, status: "completed" as const, progress: 100, projectFile }
            : f
        )
      );

      // Add to files list
      setFiles((prev) => [projectFile, ...prev]);

      // Update project file count
      setProjects((prev) =>
        prev.map((p) =>
          p.id === projectId ? { ...p, file_count: p.file_count + 1 } : p
        )
      );

      // Remove from uploading after a delay
      setTimeout(() => {
        setUploadingFiles((prev) => prev.filter((f) => f.id !== uploadId));
      }, 2000);
    } catch (err) {
      setUploadingFiles((prev) =>
        prev.map((f) =>
          f.id === uploadId
            ? { ...f, status: "error" as const, error: err instanceof Error ? err.message : "上传失败" }
            : f
        )
      );
    }
  }, []);

  const removeFile = useCallback(async (projectId: string, fileId: string) => {
    await deleteProjectFile(projectId, fileId);
    setFiles((prev) => prev.filter((f) => f.file_id !== fileId));
    setSelectedFileIds((prev) => prev.filter((id) => id !== fileId));

    // Update project file count
    setProjects((prev) =>
      prev.map((p) =>
        p.id === projectId ? { ...p, file_count: Math.max(0, p.file_count - 1) } : p
      )
    );
  }, []);

  const renameFile = useCallback(async (projectId: string, fileId: string, newName: string) => {
    const updated = await renameProjectFile(projectId, fileId, newName);
    setFiles((prev) =>
      prev.map((f) =>
        f.file_id === fileId ? { ...f, original_name: updated.original_name } : f
      )
    );
  }, []);

  const toggleFileSelection = useCallback((fileId: string) => {
    setSelectedFileIds((prev) =>
      prev.includes(fileId)
        ? prev.filter((id) => id !== fileId)
        : [...prev, fileId]
    );
  }, []);

  const selectAllFiles = useCallback(() => {
    setSelectedFileIds(files.map((f) => f.file_id));
  }, [files]);

  const clearFileSelection = useCallback(() => {
    setSelectedFileIds([]);
  }, []);

  // ==========================================================================
  // Conversation Operations (per-project caching)
  // ==========================================================================

  const getConversations = useCallback((projectId: string): ProjectConversationSummary[] => {
    return conversationsCache.get(projectId) || [];
  }, [conversationsCache]);

  const isConversationsLoading = useCallback((projectId: string): boolean => {
    return loadingProjects.has(projectId);
  }, [loadingProjects]);

  const loadConversations = useCallback(async (projectId: string) => {
    setLoadingProjects((prev) => new Set(prev).add(projectId));
    try {
      const result = await listProjectConversations(projectId);
      setConversationsCache((prev) => new Map(prev).set(projectId, result));
    } catch (err) {
      console.error("Failed to load conversations:", err);
    } finally {
      setLoadingProjects((prev) => {
        const next = new Set(prev);
        next.delete(projectId);
        return next;
      });
    }
  }, []);

  const addConversation = useCallback(async (conversationId: string, projectId: string) => {
    await addConversationToProject(conversationId, projectId);
    // Reload conversations for the project
    await loadConversations(projectId);

    // Update project conversation count
    setProjects((prev) =>
      prev.map((p) =>
        p.id === projectId ? { ...p, conversation_count: p.conversation_count + 1 } : p
      )
    );
  }, [loadConversations]);

  const removeConversation = useCallback(async (conversationId: string, projectId?: string) => {
    await removeConversationFromProject(conversationId);

    // Remove from cache
    if (projectId) {
      setConversationsCache((prev) => {
        const next = new Map(prev);
        const convs = next.get(projectId) || [];
        next.set(projectId, convs.filter((c) => c.id !== conversationId));
        return next;
      });
      // Update project conversation count
      setProjects((prev) =>
        prev.map((p) =>
          p.id === projectId ? { ...p, conversation_count: Math.max(0, p.conversation_count - 1) } : p
        )
      );
    } else if (selectedProjectId) {
      // Fallback to selectedProjectId for backward compatibility
      setConversationsCache((prev) => {
        const next = new Map(prev);
        const convs = next.get(selectedProjectId) || [];
        next.set(selectedProjectId, convs.filter((c) => c.id !== conversationId));
        return next;
      });
      setProjects((prev) =>
        prev.map((p) =>
          p.id === selectedProjectId
            ? { ...p, conversation_count: Math.max(0, p.conversation_count - 1) }
            : p
        )
      );
    }
  }, [selectedProjectId]);

  // Load projects on mount
  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    // Project list
    projects,
    isLoading,
    error,
    selectedProjectId,
    refresh,
    create,
    update,
    remove,
    select,

    // Files
    files,
    filesLoading,
    selectedFileIds,
    loadFiles,
    uploadFile: uploadFileToProject,
    removeFile,
    renameFile,
    toggleFileSelection,
    selectAllFiles,
    clearFileSelection,
    uploadingFiles,

    // Conversations (per-project caching)
    getConversations,
    isConversationsLoading,
    loadConversations,
    addConversation,
    removeConversation,
  };
}
