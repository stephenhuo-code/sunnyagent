/**
 * API client for scheduled tasks.
 */

import { apiClient } from './client';

// Types
export type ScheduleType = 'once' | 'daily' | 'weekly' | 'monthly';
export type TaskStatus = 'scheduled' | 'completed' | 'expired' | 'error';
export type ExecutionStatus = 'pending' | 'running' | 'success' | 'failed' | 'timeout';
export type DayOfWeek = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun';

export interface OnceScheduleConfig {
  run_date: string;
  run_time: string;
}

export interface DailyScheduleConfig {
  time: string;
}

export interface WeeklyScheduleConfig {
  days_of_week: DayOfWeek[];
  time: string;
}

export interface MonthlyScheduleConfig {
  days_of_month: number[];
  time: string;
}

export type ScheduleConfig =
  | OnceScheduleConfig
  | DailyScheduleConfig
  | WeeklyScheduleConfig
  | MonthlyScheduleConfig;

export interface ScheduledTask {
  id: string;
  user_id: string;
  title: string;
  schedule_type: ScheduleType;
  schedule_config: ScheduleConfig;
  expiry_date: string | null;
  enabled: boolean;
  status: TaskStatus;
  script_file_path: string;
  apscheduler_job_id: string | null;
  created_at: string;
  updated_at: string;
  next_run_time: string | null;
  last_run_time: string | null;
  last_run_status: ExecutionStatus | null;
}

export interface ScheduledTaskWithScript extends ScheduledTask {
  script_content?: string;
}

export interface CreateScheduledTaskRequest {
  title: string;
  script_content: string;
  schedule_type: ScheduleType;
  schedule_config: ScheduleConfig;
  expiry_date?: string | null;
}

export interface UpdateScheduledTaskRequest {
  title?: string;
  script_content?: string;
  schedule_type?: ScheduleType;
  schedule_config?: ScheduleConfig;
  expiry_date?: string | null;
}

export interface TaskExecution {
  id: string;
  task_id: string;
  execution_time: string;
  status: ExecutionStatus;
  duration_ms: number | null;
  retry_count: number;
  log_file_path: string | null;
  conversation_id: string | null;
  error_message: string | null;
  created_at: string;
}

export interface TaskExecutionDetail extends TaskExecution {
  log_content: string | null;
}

export interface PaginatedList<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminScheduledTask extends ScheduledTask {
  username?: string;
}

export interface ScheduledTasksSettings {
  global_enabled: boolean;
  max_concurrent_tasks: number;
  default_timeout_minutes: number;
}

export interface UpdateScheduledTasksSettingsRequest {
  global_enabled?: boolean;
  max_concurrent_tasks?: number;
  default_timeout_minutes?: number;
}

// API Functions

/**
 * List scheduled tasks for the current user.
 */
export async function listScheduledTasks(
  status?: 'scheduled' | 'completed' | 'all',
  page: number = 1,
  pageSize: number = 20
): Promise<PaginatedList<ScheduledTask>> {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  params.append('page', String(page));
  params.append('page_size', String(pageSize));

  const response = await apiClient.get(`/scheduled-tasks?${params.toString()}`);
  return response.json();
}

/**
 * Get a scheduled task by ID.
 */
export async function getScheduledTask(taskId: string): Promise<ScheduledTaskWithScript> {
  const response = await apiClient.get(`/scheduled-tasks/${taskId}`);
  return response.json();
}

/**
 * Create a new scheduled task.
 */
export async function createScheduledTask(
  data: CreateScheduledTaskRequest
): Promise<ScheduledTask> {
  const response = await apiClient.post('/scheduled-tasks', data);
  return response.json();
}

/**
 * Update a scheduled task.
 */
export async function updateScheduledTask(
  taskId: string,
  data: UpdateScheduledTaskRequest
): Promise<ScheduledTask> {
  const response = await apiClient.patch(`/scheduled-tasks/${taskId}`, data);
  return response.json();
}

/**
 * Delete a scheduled task.
 */
export async function deleteScheduledTask(taskId: string): Promise<void> {
  await apiClient.delete(`/scheduled-tasks/${taskId}`);
}

/**
 * Enable a scheduled task.
 */
export async function enableScheduledTask(taskId: string): Promise<ScheduledTask> {
  const response = await apiClient.post(`/scheduled-tasks/${taskId}/enable`);
  return response.json();
}

/**
 * Disable a scheduled task.
 */
export async function disableScheduledTask(taskId: string): Promise<ScheduledTask> {
  const response = await apiClient.post(`/scheduled-tasks/${taskId}/disable`);
  return response.json();
}

/**
 * Run a scheduled task immediately.
 */
export async function runScheduledTaskNow(taskId: string): Promise<TaskExecution> {
  const response = await apiClient.post(`/scheduled-tasks/${taskId}/run`);
  return response.json();
}

/**
 * List executions for a task.
 */
export async function listTaskExecutions(
  taskId: string,
  page: number = 1,
  pageSize: number = 20
): Promise<PaginatedList<TaskExecution>> {
  const params = new URLSearchParams();
  params.append('page', String(page));
  params.append('page_size', String(pageSize));

  const response = await apiClient.get(
    `/scheduled-tasks/${taskId}/executions?${params.toString()}`
  );
  return response.json();
}

/**
 * Get execution detail with log content.
 */
export async function getTaskExecution(
  taskId: string,
  executionId: string
): Promise<TaskExecutionDetail> {
  const response = await apiClient.get(
    `/scheduled-tasks/${taskId}/executions/${executionId}`
  );
  return response.json();
}

// Admin API Functions

/**
 * List all scheduled tasks (admin only).
 */
export async function adminListScheduledTasks(
  userId?: string,
  status?: 'scheduled' | 'completed' | 'all',
  page: number = 1,
  pageSize: number = 20
): Promise<PaginatedList<AdminScheduledTask>> {
  const params = new URLSearchParams();
  if (userId) params.append('user_id', userId);
  if (status) params.append('status', status);
  params.append('page', String(page));
  params.append('page_size', String(pageSize));

  const response = await apiClient.get(`/admin/scheduled-tasks?${params.toString()}`);
  return response.json();
}

/**
 * Get scheduled tasks global settings.
 */
export async function getScheduledTasksSettings(): Promise<ScheduledTasksSettings> {
  const response = await apiClient.get('/admin/scheduled-tasks/settings');
  return response.json();
}

/**
 * Update scheduled tasks global settings.
 */
export async function updateScheduledTasksSettings(
  data: UpdateScheduledTasksSettingsRequest
): Promise<ScheduledTasksSettings> {
  const response = await apiClient.patch('/admin/scheduled-tasks/settings', data);
  return response.json();
}

// Helper Functions

/**
 * Format schedule for display.
 */
export function formatScheduleDisplay(
  scheduleType: ScheduleType,
  scheduleConfig: ScheduleConfig
): string {
  switch (scheduleType) {
    case 'once': {
      const config = scheduleConfig as OnceScheduleConfig;
      return `${config.run_date} ${config.run_time}`;
    }
    case 'daily': {
      const config = scheduleConfig as DailyScheduleConfig;
      return `每天 ${config.time}`;
    }
    case 'weekly': {
      const config = scheduleConfig as WeeklyScheduleConfig;
      const dayNames: Record<DayOfWeek, string> = {
        mon: '周一',
        tue: '周二',
        wed: '周三',
        thu: '周四',
        fri: '周五',
        sat: '周六',
        sun: '周日',
      };
      const days = config.days_of_week.map((d) => dayNames[d]).join(', ');
      return `每周 ${days} ${config.time}`;
    }
    case 'monthly': {
      const config = scheduleConfig as MonthlyScheduleConfig;
      const days = config.days_of_month.sort((a, b) => a - b).join(', ');
      return `每月 ${days}号 ${config.time}`;
    }
    default:
      return '未知计划';
  }
}

/**
 * Format execution status for display.
 */
export function formatExecutionStatus(status: ExecutionStatus): string {
  const statusMap: Record<ExecutionStatus, string> = {
    pending: '等待中',
    running: '执行中',
    success: '成功',
    failed: '失败',
    timeout: '超时',
  };
  return statusMap[status] || status;
}

/**
 * Get status color class.
 */
export function getStatusColor(status: ExecutionStatus): string {
  const colorMap: Record<ExecutionStatus, string> = {
    pending: 'text-gray-500',
    running: 'text-blue-500',
    success: 'text-green-500',
    failed: 'text-red-500',
    timeout: 'text-orange-500',
  };
  return colorMap[status] || 'text-gray-500';
}
