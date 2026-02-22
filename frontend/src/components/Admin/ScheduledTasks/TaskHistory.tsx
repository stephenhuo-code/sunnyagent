/**
 * Task execution history modal component.
 */

import { useState } from "react";
import {
  X,
  History,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  ChevronRight,
  ChevronLeft,
} from "lucide-react";
import type {
  ScheduledTask,
  TaskExecution,
  TaskExecutionDetail,
} from "../../../api/scheduledTasks";
import { useTaskExecutions } from "../../../hooks/useScheduledTasks";
import { ExecutionDetail } from "./ExecutionDetail";
import "./ScheduledTasks.css";

interface TaskHistoryProps {
  task: ScheduledTask;
  onClose: () => void;
}

export function TaskHistory({ task, onClose }: TaskHistoryProps) {
  const { executions, total, page, isLoading, setPage } = useTaskExecutions({
    taskId: task.id,
    pageSize: 10,
  });
  const [selectedExecution, setSelectedExecution] = useState<TaskExecution | null>(null);
  const [executionDetail, setExecutionDetail] = useState<TaskExecutionDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const { getExecutionDetail } = useTaskExecutions({ taskId: task.id, autoLoad: false });

  const handleSelectExecution = async (execution: TaskExecution) => {
    setSelectedExecution(execution);
    setIsLoadingDetail(true);
    try {
      const detail = await getExecutionDetail(execution.id);
      setExecutionDetail(detail);
    } catch (err) {
      console.error("Failed to load execution detail:", err);
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircle size={16} />;
      case "failed":
        return <XCircle size={16} />;
      case "timeout":
        return <AlertCircle size={16} />;
      case "running":
        return <Loader2 size={16} className="spin" />;
      case "pending":
        return <Clock size={16} />;
      default:
        return <Clock size={16} />;
    }
  };

  const formatDuration = (ms: number | null): string => {
    if (ms === null) return "-";
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
  };

  const formatDateTime = (dateStr: string): string => {
    return new Date(dateStr).toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  const totalPages = Math.ceil(total / 10);

  if (selectedExecution && executionDetail) {
    return (
      <ExecutionDetail
        execution={executionDetail}
        onBack={() => {
          setSelectedExecution(null);
          setExecutionDetail(null);
        }}
        onClose={onClose}
      />
    );
  }

  return (
    <div className="task-form-overlay" onClick={onClose}>
      <div className="task-history-modal" onClick={(e) => e.stopPropagation()}>
        <div className="task-history-header">
          <h3>
            <History size={20} />
            执行历史 - {task.title}
          </h3>
          <button className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="task-history-content">
          {isLoading ? (
            <div className="admin-loading" style={{ padding: "48px" }}>
              <Loader2 size={32} className="spin" />
              <span>加载执行历史...</span>
            </div>
          ) : executions.length === 0 ? (
            <div className="task-list-empty" style={{ padding: "48px" }}>
              <History size={48} />
              <p>暂无执行记录</p>
              <span>任务执行后将在此显示历史记录</span>
            </div>
          ) : (
            <div className="execution-list">
              {executions.map((execution) => (
                <div
                  key={execution.id}
                  className="execution-item"
                  onClick={() => handleSelectExecution(execution)}
                >
                  <div className={`execution-status-icon ${execution.status}`}>
                    {getStatusIcon(execution.status)}
                  </div>
                  <div className="execution-info">
                    <div className="execution-time">
                      {formatDateTime(execution.execution_time)}
                    </div>
                    <div className="execution-meta">
                      <span className="execution-duration">
                        <Clock size={12} />
                        {formatDuration(execution.duration_ms)}
                      </span>
                      {execution.retry_count > 0 && (
                        <span>重试 {execution.retry_count} 次</span>
                      )}
                    </div>
                  </div>
                  <ChevronRight size={16} className="execution-arrow" />
                </div>
              ))}
            </div>
          )}
        </div>

        {totalPages > 1 && (
          <div className="task-pagination">
            <button
              className="pagination-btn"
              onClick={() => setPage(page - 1)}
              disabled={page <= 1}
            >
              <ChevronLeft size={16} />
            </button>
            <span className="pagination-info">
              {page} / {totalPages}
            </span>
            <button
              className="pagination-btn"
              onClick={() => setPage(page + 1)}
              disabled={page >= totalPages}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
