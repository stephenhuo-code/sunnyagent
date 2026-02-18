/**
 * API client for project management
 */

import { handleUnauthorized } from '../hooks/useAuth';

function checkUnauthorized(res: Response) {
  if (res.status === 401) {
    handleUnauthorized();
  }
}

// =============================================================================
// Types
// =============================================================================

export interface ProjectSummary {
  id: string;
  name: string;
  creator_name: string;
  file_count: number;
  conversation_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail {
  id: string;
  name: string;
  creator_name: string;
  file_count: number;
  conversation_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectFileSummary {
  id: string;
  file_id: string;
  original_name: string;
  content_type: string | null;
  size_bytes: number;
  created_at: string;
  download_url: string;
}

export interface ProjectConversationSummary {
  id: string;
  title: string;
  updated_at: string;
}

export interface FileUploadResponse {
  id: string;
  file_id: string;
  original_name: string;
  content_type: string | null;
  size_bytes: number;
  download_url: string;
}

// =============================================================================
// Project CRUD
// =============================================================================

/**
 * List all projects for the current user
 */
export async function listProjects(): Promise<ProjectSummary[]> {
  const res = await fetch('/api/projects', {
    credentials: 'include',
  });
  checkUnauthorized(res);
  if (!res.ok) {
    throw new Error('Failed to list projects');
  }
  return res.json();
}

/**
 * Get a project by ID
 */
export async function getProject(id: string): Promise<ProjectDetail> {
  const res = await fetch(`/api/projects/${id}`, {
    credentials: 'include',
  });
  checkUnauthorized(res);
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error('项目不存在');
    }
    throw new Error('Failed to get project');
  }
  return res.json();
}

/**
 * Create a new project
 */
export async function createProject(name: string): Promise<ProjectDetail> {
  const res = await fetch('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ name }),
  });
  checkUnauthorized(res);
  if (!res.ok) {
    if (res.status === 400) {
      const data = await res.json();
      throw new Error(data.detail || '创建项目失败');
    }
    throw new Error('Failed to create project');
  }
  return res.json();
}

/**
 * Update a project's name
 */
export async function updateProject(id: string, name: string): Promise<ProjectDetail> {
  const res = await fetch(`/api/projects/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ name }),
  });
  checkUnauthorized(res);
  if (!res.ok) {
    if (res.status === 400) {
      const data = await res.json();
      throw new Error(data.detail || '更新项目失败');
    }
    if (res.status === 404) {
      throw new Error('项目不存在');
    }
    throw new Error('Failed to update project');
  }
  return res.json();
}

/**
 * Delete a project
 */
export async function deleteProject(id: string): Promise<void> {
  const res = await fetch(`/api/projects/${id}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  checkUnauthorized(res);
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error('项目不存在');
    }
    throw new Error('Failed to delete project');
  }
}

// =============================================================================
// Project Files
// =============================================================================

/**
 * List files in a project
 */
export async function listProjectFiles(projectId: string): Promise<ProjectFileSummary[]> {
  const res = await fetch(`/api/projects/${projectId}/files`, {
    credentials: 'include',
  });
  checkUnauthorized(res);
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error('项目不存在');
    }
    throw new Error('Failed to list project files');
  }
  return res.json();
}

/**
 * Upload a file to a project
 */
export async function uploadProjectFile(
  projectId: string,
  file: File,
  onProgress?: (progress: number) => void
): Promise<FileUploadResponse> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/api/projects/${projectId}/files`);
    xhr.withCredentials = true;

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status === 201) {
        resolve(JSON.parse(xhr.responseText));
      } else if (xhr.status === 401) {
        handleUnauthorized();
        reject(new Error('Unauthorized'));
      } else if (xhr.status === 400) {
        const data = JSON.parse(xhr.responseText);
        reject(new Error(data.detail || '上传失败'));
      } else if (xhr.status === 404) {
        reject(new Error('项目不存在'));
      } else {
        reject(new Error('上传失败'));
      }
    };

    xhr.onerror = () => reject(new Error('上传失败'));
    xhr.send(formData);
  });
}

/**
 * Delete a file from a project
 */
export async function deleteProjectFile(projectId: string, fileId: string): Promise<void> {
  const res = await fetch(`/api/projects/${projectId}/files/${fileId}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  checkUnauthorized(res);
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error('文件不存在');
    }
    throw new Error('Failed to delete file');
  }
}

/**
 * Rename a file in a project
 */
export async function renameProjectFile(
  projectId: string,
  fileId: string,
  newName: string
): Promise<ProjectFileSummary> {
  const res = await fetch(`/api/projects/${projectId}/files/${fileId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ name: newName }),
  });
  checkUnauthorized(res);
  if (!res.ok) {
    if (res.status === 400) {
      const data = await res.json();
      throw new Error(data.detail || '重命名失败');
    }
    if (res.status === 404) {
      throw new Error('文件不存在');
    }
    throw new Error('Failed to rename file');
  }
  return res.json();
}

// =============================================================================
// Project Conversations
// =============================================================================

/**
 * List conversations in a project
 */
export async function listProjectConversations(
  projectId: string
): Promise<ProjectConversationSummary[]> {
  const res = await fetch(`/api/projects/${projectId}/conversations`, {
    credentials: 'include',
  });
  checkUnauthorized(res);
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error('项目不存在');
    }
    throw new Error('Failed to list project conversations');
  }
  return res.json();
}

/**
 * Add a conversation to a project
 */
export async function addConversationToProject(
  conversationId: string,
  projectId: string
): Promise<void> {
  const res = await fetch(`/api/conversations/${conversationId}/project`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ project_id: projectId }),
  });
  checkUnauthorized(res);
  if (!res.ok) {
    if (res.status === 400) {
      const data = await res.json();
      throw new Error(data.detail || '添加失败');
    }
    if (res.status === 404) {
      throw new Error('对话或项目不存在');
    }
    throw new Error('Failed to add conversation to project');
  }
}

/**
 * Remove a conversation from its project
 */
export async function removeConversationFromProject(conversationId: string): Promise<void> {
  const res = await fetch(`/api/conversations/${conversationId}/project`, {
    method: 'DELETE',
    credentials: 'include',
  });
  checkUnauthorized(res);
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error('对话不存在');
    }
    throw new Error('Failed to remove conversation from project');
  }
}
