/**
 * Task list component with tabs and status filtering.
 */

import { Clock, Loader2 } from "lucide-react";
import type { ScheduledTask } from "../../../api/scheduledTasks";
import { TaskListItem } from "./TaskListItem";
import "./ScheduledTasks.css";

interface TaskListProps {
  tasks: ScheduledTask[];
  total: number;
  isLoading: boolean;
  statusFilter: "scheduled" | "completed" | "all";
  onStatusFilterChange: (status: "scheduled" | "completed" | "all") => void;
  onToggleEnabled: (taskId: string, enabled: boolean) => Promise<void>;
  onRunNow: (taskId: string) => Promise<void>;
  onEdit: (task: ScheduledTask) => void;
  onHistory: (task: ScheduledTask) => void;
  onDelete: (task: ScheduledTask) => void;
}

export function TaskList({
  tasks,
  total,
  isLoading,
  statusFilter,
  onStatusFilterChange,
  onToggleEnabled,
  onRunNow,
  onEdit,
  onHistory,
  onDelete,
}: TaskListProps) {
  const scheduledCount = tasks.filter(
    (t) => t.status === "scheduled" || t.status === "error"
  ).length;
  const completedCount = tasks.filter(
    (t) => t.status === "completed" || t.status === "expired"
  ).length;

  if (isLoading && tasks.length === 0) {
    return (
      <div className="admin-loading">
        <Loader2 size={32} className="spin" />
        <span>加载任务中...</span>
      </div>
    );
  }

  return (
    <div className="task-list-wrapper">
      <div className="task-tabs">
        <button
          className={`task-tab ${statusFilter === "scheduled" ? "active" : ""}`}
          onClick={() => onStatusFilterChange("scheduled")}
        >
          已定时
          <span className="task-tab-count">{scheduledCount || total}</span>
        </button>
        <button
          className={`task-tab ${statusFilter === "completed" ? "active" : ""}`}
          onClick={() => onStatusFilterChange("completed")}
        >
          已完成
          <span className="task-tab-count">{completedCount || 0}</span>
        </button>
        <button
          className={`task-tab ${statusFilter === "all" ? "active" : ""}`}
          onClick={() => onStatusFilterChange("all")}
        >
          全部
          <span className="task-tab-count">{total}</span>
        </button>
      </div>

      <div className="task-list-container">
        {tasks.length === 0 ? (
          <div className="task-list-empty">
            <Clock size={48} />
            <p>
              {statusFilter === "scheduled"
                ? "暂无已定时的任务"
                : statusFilter === "completed"
                  ? "暂无已完成的任务"
                  : "暂无任务"}
            </p>
            <span>点击右上角按钮创建新的定时任务</span>
          </div>
        ) : (
          <div className="task-list">
            {tasks.map((task) => (
              <TaskListItem
                key={task.id}
                task={task}
                onToggleEnabled={onToggleEnabled}
                onRunNow={onRunNow}
                onEdit={onEdit}
                onHistory={onHistory}
                onDelete={onDelete}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
