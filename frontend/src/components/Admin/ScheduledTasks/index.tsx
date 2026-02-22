/**
 * Scheduled Tasks management page component.
 */

import { useState } from "react";
import { Clock, Plus, AlertCircle, X } from "lucide-react";
import { useScheduledTasks } from "../../../hooks/useScheduledTasks";
import type {
  ScheduledTask,
  ScheduledTaskWithScript,
  CreateScheduledTaskRequest,
  UpdateScheduledTaskRequest,
} from "../../../api/scheduledTasks";
import { TaskForm } from "./TaskForm";
import { TaskList } from "./TaskList";
import { TaskHistory } from "./TaskHistory";
import "../Admin.css";
import "./ScheduledTasks.css";

export function ScheduledTasks() {
  const {
    tasks,
    total,
    isLoading,
    error,
    createTask,
    updateTask,
    deleteTask,
    toggleEnabled,
    runNow,
    getTask,
    setStatusFilter,
    clearError,
  } = useScheduledTasks();

  const [statusFilter, setLocalStatusFilter] = useState<"scheduled" | "completed" | "all">(
    "scheduled"
  );
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingTask, setEditingTask] = useState<ScheduledTaskWithScript | null>(null);
  const [historyTask, setHistoryTask] = useState<ScheduledTask | null>(null);
  const [deleteConfirmTask, setDeleteConfirmTask] = useState<ScheduledTask | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleStatusFilterChange = (status: "scheduled" | "completed" | "all") => {
    setLocalStatusFilter(status);
    setStatusFilter(status);
  };

  const handleCreateTask = async (data: CreateScheduledTaskRequest) => {
    await createTask(data);
    setShowCreateForm(false);
  };

  const handleEditTask = async (task: ScheduledTask) => {
    try {
      const fullTask = await getTask(task.id);
      setEditingTask(fullTask);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "获取任务详情失败");
    }
  };

  const handleUpdateTask = async (data: UpdateScheduledTaskRequest) => {
    if (!editingTask) return;
    await updateTask(editingTask.id, data);
    setEditingTask(null);
  };

  const handleDeleteTask = async () => {
    if (!deleteConfirmTask) return;
    setIsDeleting(true);
    try {
      await deleteTask(deleteConfirmTask.id);
      setDeleteConfirmTask(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "删除任务失败");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleToggleEnabled = async (taskId: string, enabled: boolean) => {
    try {
      await toggleEnabled(taskId, enabled);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "切换任务状态失败");
    }
  };

  const handleRunNow = async (taskId: string) => {
    try {
      await runNow(taskId);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "执行任务失败");
    }
  };

  return (
    <div className="scheduled-tasks">
      <div className="admin-header">
        <div className="admin-title">
          <Clock size={24} />
          <h1>定时任务</h1>
        </div>
      </div>

      <div className="admin-toolbar">
        <button className="btn-primary" onClick={() => setShowCreateForm(true)}>
          <Plus size={18} />
          创建任务
        </button>
      </div>

      {(error || actionError) && (
        <div className="admin-error">
          <AlertCircle size={18} />
          <span>{error || actionError}</span>
          <button
            onClick={() => {
              clearError();
              setActionError(null);
            }}
          >
            <X size={16} />
          </button>
        </div>
      )}

      <TaskList
        tasks={tasks}
        total={total}
        isLoading={isLoading}
        statusFilter={statusFilter}
        onStatusFilterChange={handleStatusFilterChange}
        onToggleEnabled={handleToggleEnabled}
        onRunNow={handleRunNow}
        onEdit={handleEditTask}
        onHistory={setHistoryTask}
        onDelete={setDeleteConfirmTask}
      />

      {showCreateForm && (
        <TaskForm
          onSubmit={handleCreateTask}
          onCancel={() => setShowCreateForm(false)}
        />
      )}

      {editingTask && (
        <TaskForm
          task={editingTask}
          onSubmit={handleUpdateTask}
          onCancel={() => setEditingTask(null)}
        />
      )}

      {historyTask && (
        <TaskHistory task={historyTask} onClose={() => setHistoryTask(null)} />
      )}

      {deleteConfirmTask && (
        <div className="delete-confirm-overlay" onClick={() => setDeleteConfirmTask(null)}>
          <div className="delete-confirm-modal" onClick={(e) => e.stopPropagation()}>
            <h4>确认删除</h4>
            <p>确定要删除任务 "{deleteConfirmTask.title}" 吗？此操作不可撤销。</p>
            <div className="delete-confirm-actions">
              <button
                className="btn-secondary"
                onClick={() => setDeleteConfirmTask(null)}
                disabled={isDeleting}
              >
                取消
              </button>
              <button
                className="btn-danger"
                onClick={handleDeleteTask}
                disabled={isDeleting}
              >
                {isDeleting ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export { TaskForm } from "./TaskForm";
export { TaskList } from "./TaskList";
export { TaskListItem } from "./TaskListItem";
export { TaskHistory } from "./TaskHistory";
export { ExecutionDetail } from "./ExecutionDetail";
export { ScheduleInputs } from "./ScheduleInputs";
export { AdminTaskList } from "./AdminTaskList";
