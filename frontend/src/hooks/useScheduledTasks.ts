/**
 * React hooks for scheduled tasks management.
 */

import { useState, useCallback, useEffect } from "react";
import {
  listScheduledTasks,
  getScheduledTask,
  createScheduledTask,
  updateScheduledTask,
  deleteScheduledTask,
  enableScheduledTask,
  disableScheduledTask,
  runScheduledTaskNow,
  listTaskExecutions,
  getTaskExecution,
  type ScheduledTask,
  type ScheduledTaskWithScript,
  type CreateScheduledTaskRequest,
  type UpdateScheduledTaskRequest,
  type TaskExecution,
  type TaskExecutionDetail,
} from "../api/scheduledTasks";

interface UseScheduledTasksOptions {
  autoLoad?: boolean;
  statusFilter?: "scheduled" | "completed" | "all";
  pageSize?: number;
}

interface UseScheduledTasksReturn {
  // State
  tasks: ScheduledTask[];
  total: number;
  page: number;
  isLoading: boolean;
  error: string | null;

  // Actions
  loadTasks: (page?: number, status?: string) => Promise<void>;
  createTask: (data: CreateScheduledTaskRequest) => Promise<ScheduledTask>;
  updateTask: (taskId: string, data: UpdateScheduledTaskRequest) => Promise<ScheduledTask>;
  deleteTask: (taskId: string) => Promise<void>;
  toggleEnabled: (taskId: string, enabled: boolean) => Promise<ScheduledTask>;
  runNow: (taskId: string) => Promise<TaskExecution>;
  getTask: (taskId: string) => Promise<ScheduledTaskWithScript>;
  setPage: (page: number) => void;
  setStatusFilter: (status: "scheduled" | "completed" | "all") => void;
  clearError: () => void;
}

export function useScheduledTasks(
  options: UseScheduledTasksOptions = {}
): UseScheduledTasksReturn {
  const {
    autoLoad = true,
    statusFilter: initialStatus = "scheduled",
    pageSize = 20,
  } = options;

  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<"scheduled" | "completed" | "all">(
    initialStatus
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTasks = useCallback(
    async (loadPage?: number, status?: string) => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await listScheduledTasks(
          (status as "scheduled" | "completed" | "all") || statusFilter,
          loadPage || page,
          pageSize
        );
        setTasks(result.items);
        setTotal(result.total);
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载任务列表失败");
      } finally {
        setIsLoading(false);
      }
    },
    [page, pageSize, statusFilter]
  );

  useEffect(() => {
    if (autoLoad) {
      loadTasks();
    }
  }, [autoLoad, page, statusFilter, loadTasks]);

  const handleSetPage = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  const handleSetStatusFilter = useCallback(
    (status: "scheduled" | "completed" | "all") => {
      setStatusFilter(status);
      setPage(1);
    },
    []
  );

  const createTask = useCallback(
    async (data: CreateScheduledTaskRequest): Promise<ScheduledTask> => {
      const task = await createScheduledTask(data);
      // Reload tasks to get fresh data
      await loadTasks(1, statusFilter);
      return task;
    },
    [loadTasks, statusFilter]
  );

  const updateTask = useCallback(
    async (taskId: string, data: UpdateScheduledTaskRequest): Promise<ScheduledTask> => {
      const task = await updateScheduledTask(taskId, data);
      // Update local state
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, ...task } : t))
      );
      return task;
    },
    []
  );

  const deleteTask = useCallback(
    async (taskId: string): Promise<void> => {
      await deleteScheduledTask(taskId);
      // Remove from local state
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
      setTotal((prev) => prev - 1);
    },
    []
  );

  const toggleEnabled = useCallback(
    async (taskId: string, enabled: boolean): Promise<ScheduledTask> => {
      const task = enabled
        ? await enableScheduledTask(taskId)
        : await disableScheduledTask(taskId);
      // Update local state
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, enabled: task.enabled } : t))
      );
      return task;
    },
    []
  );

  const runNow = useCallback(async (taskId: string): Promise<TaskExecution> => {
    return await runScheduledTaskNow(taskId);
  }, []);

  const getTask = useCallback(
    async (taskId: string): Promise<ScheduledTaskWithScript> => {
      return await getScheduledTask(taskId);
    },
    []
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    tasks,
    total,
    page,
    isLoading,
    error,
    loadTasks,
    createTask,
    updateTask,
    deleteTask,
    toggleEnabled,
    runNow,
    getTask,
    setPage: handleSetPage,
    setStatusFilter: handleSetStatusFilter,
    clearError,
  };
}

// Hook for execution history
interface UseTaskExecutionsOptions {
  taskId: string;
  autoLoad?: boolean;
  pageSize?: number;
}

interface UseTaskExecutionsReturn {
  executions: TaskExecution[];
  total: number;
  page: number;
  isLoading: boolean;
  error: string | null;
  loadExecutions: (page?: number) => Promise<void>;
  getExecutionDetail: (executionId: string) => Promise<TaskExecutionDetail>;
  setPage: (page: number) => void;
}

export function useTaskExecutions(
  options: UseTaskExecutionsOptions
): UseTaskExecutionsReturn {
  const { taskId, autoLoad = true, pageSize = 20 } = options;

  const [executions, setExecutions] = useState<TaskExecution[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadExecutions = useCallback(
    async (loadPage?: number) => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await listTaskExecutions(taskId, loadPage || page, pageSize);
        setExecutions(result.items);
        setTotal(result.total);
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载执行历史失败");
      } finally {
        setIsLoading(false);
      }
    },
    [taskId, page, pageSize]
  );

  useEffect(() => {
    if (autoLoad) {
      loadExecutions();
    }
  }, [autoLoad, page, loadExecutions]);

  const handleSetPage = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  const getExecutionDetail = useCallback(
    async (executionId: string): Promise<TaskExecutionDetail> => {
      return await getTaskExecution(taskId, executionId);
    },
    [taskId]
  );

  return {
    executions,
    total,
    page,
    isLoading,
    error,
    loadExecutions,
    getExecutionDetail,
    setPage: handleSetPage,
  };
}
