/**
 * Form for creating and editing scheduled tasks.
 */

import { useState, useEffect } from "react";
import { Clock, X, Calendar } from "lucide-react";
import type {
  ScheduleType,
  ScheduleConfig,
  CreateScheduledTaskRequest,
  UpdateScheduledTaskRequest,
  ScheduledTaskWithScript,
} from "../../../api/scheduledTasks";
import { ScheduleInputs, getDefaultScheduleConfig } from "./ScheduleInputs";
import "../Admin.css";
import "./ScheduledTasks.css";

interface TaskFormProps {
  task?: ScheduledTaskWithScript;
  prefillPrompt?: string;
  prefillScheduleType?: ScheduleType;
  prefillScheduleConfig?: ScheduleConfig;
  onSubmit: (data: CreateScheduledTaskRequest | UpdateScheduledTaskRequest) => Promise<void>;
  onCancel: () => void;
}

const SCHEDULE_TYPE_OPTIONS: { value: ScheduleType; label: string; description: string }[] = [
  { value: "once", label: "单次执行", description: "在指定日期时间执行一次" },
  { value: "daily", label: "每天执行", description: "每天在指定时间执行" },
  { value: "weekly", label: "每周执行", description: "每周选定的日期执行" },
  { value: "monthly", label: "每月执行", description: "每月选定的日期执行" },
];

export function TaskForm({
  task,
  prefillPrompt,
  prefillScheduleType,
  prefillScheduleConfig,
  onSubmit,
  onCancel,
}: TaskFormProps) {
  const isEditing = !!task;

  const [title, setTitle] = useState(task?.title || "");
  const [scriptContent, setScriptContent] = useState(
    task?.script_content || prefillPrompt || ""
  );
  const [scheduleType, setScheduleType] = useState<ScheduleType>(
    task?.schedule_type || prefillScheduleType || "daily"
  );
  const [scheduleConfig, setScheduleConfig] = useState<ScheduleConfig>(
    task?.schedule_config || prefillScheduleConfig || getDefaultScheduleConfig("daily")
  );
  const [expiryDate, setExpiryDate] = useState<string>(
    task?.expiry_date ? task.expiry_date.split("T")[0] : ""
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Update schedule config when schedule type changes
  useEffect(() => {
    if (!task) {
      setScheduleConfig(getDefaultScheduleConfig(scheduleType));
    }
  }, [scheduleType, task]);

  const handleScheduleTypeChange = (type: ScheduleType) => {
    setScheduleType(type);
    if (!task) {
      setScheduleConfig(getDefaultScheduleConfig(type));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!title.trim()) {
      setError("请输入任务标题");
      return;
    }
    if (!scriptContent.trim()) {
      setError("请输入执行内容");
      return;
    }

    setIsSubmitting(true);
    try {
      if (isEditing) {
        const updateData: UpdateScheduledTaskRequest = {
          title: title.trim(),
          script_content: scriptContent.trim(),
          schedule_type: scheduleType,
          schedule_config: scheduleConfig,
          expiry_date: expiryDate || null,
        };
        await onSubmit(updateData);
      } else {
        const createData: CreateScheduledTaskRequest = {
          title: title.trim(),
          script_content: scriptContent.trim(),
          schedule_type: scheduleType,
          schedule_config: scheduleConfig,
          expiry_date: expiryDate || null,
        };
        await onSubmit(createData);
      }
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(isEditing ? "更新任务失败" : "创建任务失败");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="task-form-overlay" onClick={onCancel}>
      <div className="task-form-modal" onClick={(e) => e.stopPropagation()}>
        <div className="task-form-header">
          <h3>
            <Clock size={20} />
            {isEditing ? "编辑定时任务" : "创建定时任务"}
          </h3>
          <button className="close-btn" onClick={onCancel}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="task-form-content">
          <div className="form-field">
            <label htmlFor="title">任务标题</label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例如：每日新闻摘要"
              autoFocus
              disabled={isSubmitting}
            />
          </div>

          <div className="form-field">
            <label htmlFor="script_content">执行内容（Prompt）</label>
            <textarea
              id="script_content"
              value={scriptContent}
              onChange={(e) => setScriptContent(e.target.value)}
              placeholder="请输入要执行的 AI 指令，例如：分析今日科技新闻，并总结主要趋势"
              rows={4}
              disabled={isSubmitting}
            />
          </div>

          <div className="form-field">
            <label>计划类型</label>
            <div className="schedule-type-selector">
              {SCHEDULE_TYPE_OPTIONS.map(({ value, label, description }) => (
                <button
                  key={value}
                  type="button"
                  className={`schedule-type-btn ${scheduleType === value ? "selected" : ""}`}
                  onClick={() => handleScheduleTypeChange(value)}
                  disabled={isSubmitting}
                >
                  <span className="schedule-type-label">{label}</span>
                  <span className="schedule-type-desc">{description}</span>
                </button>
              ))}
            </div>
          </div>

          <ScheduleInputs
            scheduleType={scheduleType}
            scheduleConfig={scheduleConfig}
            onChange={setScheduleConfig}
            disabled={isSubmitting}
          />

          <div className="form-field">
            <label htmlFor="expiry_date">
              <Calendar size={14} style={{ marginRight: 6 }} />
              过期日期（可选）
            </label>
            <input
              id="expiry_date"
              type="date"
              value={expiryDate}
              onChange={(e) => setExpiryDate(e.target.value)}
              disabled={isSubmitting}
              min={new Date().toISOString().split("T")[0]}
            />
            <p className="input-hint">任务将在此日期后自动停止执行</p>
          </div>

          {error && <div className="form-error">{error}</div>}

          <div className="form-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={onCancel}
              disabled={isSubmitting}
            >
              取消
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={isSubmitting}
            >
              {isSubmitting
                ? isEditing
                  ? "保存中..."
                  : "创建中..."
                : isEditing
                  ? "保存任务"
                  : "创建任务"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
