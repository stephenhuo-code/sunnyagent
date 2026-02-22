/**
 * Execution detail modal with log viewer.
 */

import { X, FileText, ArrowLeft } from "lucide-react";
import type { TaskExecutionDetail } from "../../../api/scheduledTasks";
import { formatExecutionStatus } from "../../../api/scheduledTasks";
import "./ScheduledTasks.css";

interface ExecutionDetailProps {
  execution: TaskExecutionDetail;
  onBack: () => void;
  onClose: () => void;
}

export function ExecutionDetail({ execution, onBack, onClose }: ExecutionDetailProps) {
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

  const formatDuration = (ms: number | null): string => {
    if (ms === null) return "-";
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
  };

  return (
    <div className="task-form-overlay" onClick={onClose}>
      <div className="execution-detail-modal" onClick={(e) => e.stopPropagation()}>
        <div className="execution-detail-header">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              className="close-btn"
              onClick={onBack}
              style={{ position: "relative", top: 0, right: 0 }}
            >
              <ArrowLeft size={20} />
            </button>
            <h3>
              <FileText size={20} />
              执行详情
            </h3>
          </div>
          <button className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="execution-detail-content">
          <div className="execution-detail-info">
            <div className="detail-item">
              <span className="detail-label">状态</span>
              <span className={`detail-value ${execution.status}`}>
                {formatExecutionStatus(execution.status)}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">执行时间</span>
              <span className="detail-value">
                {formatDateTime(execution.execution_time)}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">执行时长</span>
              <span className="detail-value">
                {formatDuration(execution.duration_ms)}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">重试次数</span>
              <span className="detail-value">{execution.retry_count}</span>
            </div>
            {execution.error_message && (
              <div className="detail-item" style={{ gridColumn: "1 / -1" }}>
                <span className="detail-label">错误信息</span>
                <span className="detail-value failed">{execution.error_message}</span>
              </div>
            )}
          </div>

          <div className="log-section">
            <h4>执行日志</h4>
            <div className="log-content">
              {execution.log_content ? (
                execution.log_content
              ) : (
                <span className="log-empty">暂无日志内容</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
