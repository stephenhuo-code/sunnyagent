/**
 * Individual task item in the task list.
 */

import { useState } from "react";
import {
  Clock,
  Play,
  Edit,
  History,
  Trash2,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import type { ScheduledTask, ExecutionStatus } from "../../../api/scheduledTasks";
import { formatScheduleDisplay } from "../../../api/scheduledTasks";
import "./ScheduledTasks.css";

interface TaskListItemProps {
  task: ScheduledTask;
  onToggleEnabled: (taskId: string, enabled: boolean) => Promise<void>;
  onRunNow: (taskId: string) => Promise<void>;
  onEdit: (task: ScheduledTask) => void;
  onHistory: (task: ScheduledTask) => void;
  onDelete: (task: ScheduledTask) => void;
  disabled?: boolean;
}

export function TaskListItem({
  task,
  onToggleEnabled,
  onRunNow,
  onEdit,
  onHistory,
  onDelete,
  disabled = false,
}: TaskListItemProps) {
  const [isToggling, setIsToggling] = useState(false);
  const [isRunning, setIsRunning] = useState(false);

  const handleToggle = async () => {
    setIsToggling(true);
    try {
      await onToggleEnabled(task.id, !task.enabled);
    } finally {
      setIsToggling(false);
    }
  };

  const handleRunNow = async () => {
    setIsRunning(true);
    try {
      await onRunNow(task.id);
    } finally {
      setIsRunning(false);
    }
  };

  const formatNextRun = (nextRunTime: string | null): string => {
    if (!nextRunTime) return "未计划";
    const date = new Date(nextRunTime);
    const now = new Date();
    const diff = date.getTime() - now.getTime();

    if (diff < 0) return "已过期";
    if (diff < 60000) return "即将执行";
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟后`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时后`;

    return date.toLocaleString("zh-CN", {
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getLastRunStatusIcon = (status: ExecutionStatus | null) => {
    switch (status) {
      case "success":
        return <CheckCircle size={14} />;
      case "failed":
        return <XCircle size={14} />;
      case "timeout":
        return <AlertCircle size={14} />;
      case "running":
        return <Loader2 size={14} className="spin" />;
      case "pending":
        return <Clock size={14} />;
      default:
        return null;
    }
  };

  const getLastRunStatusText = (status: ExecutionStatus | null): string => {
    switch (status) {
      case "success":
        return "成功";
      case "failed":
        return "失败";
      case "timeout":
        return "超时";
      case "running":
        return "执行中";
      case "pending":
        return "等待中";
      default:
        return "";
    }
  };

  return (
    <div className={`task-list-item ${!task.enabled ? "disabled" : ""}`}>
      <div className="task-info">
        <h4 className="task-title">{task.title}</h4>
        <div className="task-schedule">
          <Clock size={14} />
          <span>{formatScheduleDisplay(task.schedule_type, task.schedule_config)}</span>
        </div>
      </div>

      <div className="task-meta">
        {task.enabled && task.next_run_time && (
          <span className="task-next-run">
            下次: {formatNextRun(task.next_run_time)}
          </span>
        )}
        {task.last_run_status && (
          <span className={`task-last-run ${task.last_run_status}`}>
            {getLastRunStatusIcon(task.last_run_status)}
            <span>{getLastRunStatusText(task.last_run_status)}</span>
          </span>
        )}
      </div>

      <button
        className={`task-toggle ${task.enabled ? "enabled" : ""}`}
        onClick={handleToggle}
        disabled={disabled || isToggling}
        title={task.enabled ? "禁用任务" : "启用任务"}
      >
        <span className="task-toggle-knob" />
      </button>

      <div className="task-actions">
        <button
          className="task-action-btn play"
          onClick={handleRunNow}
          disabled={disabled || isRunning}
          title="立即执行"
        >
          {isRunning ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
        </button>
        <button
          className="task-action-btn edit"
          onClick={() => onEdit(task)}
          disabled={disabled}
          title="编辑任务"
        >
          <Edit size={16} />
        </button>
        <button
          className="task-action-btn history"
          onClick={() => onHistory(task)}
          disabled={disabled}
          title="执行历史"
        >
          <History size={16} />
        </button>
        <button
          className="task-action-btn delete"
          onClick={() => onDelete(task)}
          disabled={disabled}
          title="删除任务"
        >
          <Trash2 size={16} />
        </button>
      </div>
    </div>
  );
}
