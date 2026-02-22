/**
 * Admin view for all users' scheduled tasks (read-only).
 */

import { useState, useEffect, useCallback } from 'react';
import {
  adminListScheduledTasks,
  getScheduledTasksSettings,
  updateScheduledTasksSettings,
  formatScheduleDisplay,
  type AdminScheduledTask,
  type ScheduledTasksSettings,
} from '../../../api/scheduledTasks';
import './ScheduledTasks.css';

interface AdminTaskListProps {
  className?: string;
}

export function AdminTaskList({ className = '' }: AdminTaskListProps) {
  const [tasks, setTasks] = useState<AdminScheduledTask[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<'scheduled' | 'completed' | 'all'>('all');
  const [settings, setSettings] = useState<ScheduledTasksSettings | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminListScheduledTasks(undefined, statusFilter, page, pageSize);
      setTasks(result.items);
      setTotal(result.total);
    } catch (error) {
      console.error('Failed to fetch admin tasks:', error);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page, pageSize]);

  const fetchSettings = useCallback(async () => {
    setSettingsLoading(true);
    try {
      const result = await getScheduledTasksSettings();
      setSettings(result);
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    } finally {
      setSettingsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleToggleGlobalEnabled = async () => {
    if (!settings) return;
    try {
      const updated = await updateScheduledTasksSettings({
        global_enabled: !settings.global_enabled,
      });
      setSettings(updated);
    } catch (error) {
      console.error('Failed to update settings:', error);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  const getStatusBadge = (task: AdminScheduledTask) => {
    const statusConfig = {
      scheduled: { label: '已定时', className: 'badge-scheduled' },
      completed: { label: '已完成', className: 'badge-completed' },
      expired: { label: '已过期', className: 'badge-expired' },
      error: { label: '错误', className: 'badge-error' },
    };
    const config = statusConfig[task.status] || { label: task.status, className: '' };
    return <span className={`task-badge ${config.className}`}>{config.label}</span>;
  };

  return (
    <div className={`admin-task-list ${className}`}>
      {/* Global Settings Section */}
      <div className="admin-settings-section">
        <h3>全局设置</h3>
        {settingsLoading ? (
          <div className="loading-text">加载中...</div>
        ) : settings ? (
          <div className="settings-grid">
            <div className="setting-item">
              <label>全局启用</label>
              <button
                className={`toggle-btn ${settings.global_enabled ? 'active' : ''}`}
                onClick={handleToggleGlobalEnabled}
              >
                {settings.global_enabled ? '已启用' : '已禁用'}
              </button>
            </div>
            <div className="setting-item">
              <label>最大并发任务</label>
              <span className="setting-value">{settings.max_concurrent_tasks}</span>
            </div>
            <div className="setting-item">
              <label>默认超时时间</label>
              <span className="setting-value">{settings.default_timeout_minutes} 分钟</span>
            </div>
          </div>
        ) : null}
      </div>

      {/* Task List Section */}
      <div className="admin-tasks-section">
        <div className="admin-tasks-header">
          <h3>所有用户任务</h3>
          <div className="filter-tabs">
            <button
              className={`filter-tab ${statusFilter === 'all' ? 'active' : ''}`}
              onClick={() => { setStatusFilter('all'); setPage(1); }}
            >
              全部 ({total})
            </button>
            <button
              className={`filter-tab ${statusFilter === 'scheduled' ? 'active' : ''}`}
              onClick={() => { setStatusFilter('scheduled'); setPage(1); }}
            >
              已定时
            </button>
            <button
              className={`filter-tab ${statusFilter === 'completed' ? 'active' : ''}`}
              onClick={() => { setStatusFilter('completed'); setPage(1); }}
            >
              已完成
            </button>
          </div>
        </div>

        {loading ? (
          <div className="loading-text">加载中...</div>
        ) : tasks.length === 0 ? (
          <div className="empty-state">暂无任务</div>
        ) : (
          <div className="admin-task-table">
            <table>
              <thead>
                <tr>
                  <th>标题</th>
                  <th>用户</th>
                  <th>计划</th>
                  <th>状态</th>
                  <th>启用</th>
                  <th>下次执行</th>
                  <th>上次执行</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.id}>
                    <td className="task-title-cell">{task.title}</td>
                    <td className="task-user-cell">{task.username || task.user_id.slice(0, 8)}</td>
                    <td className="task-schedule-cell">
                      {formatScheduleDisplay(task.schedule_type, task.schedule_config)}
                    </td>
                    <td className="task-status-cell">{getStatusBadge(task)}</td>
                    <td className="task-enabled-cell">
                      <span className={`enabled-indicator ${task.enabled ? 'enabled' : 'disabled'}`}>
                        {task.enabled ? '是' : '否'}
                      </span>
                    </td>
                    <td className="task-time-cell">
                      {task.next_run_time
                        ? new Date(task.next_run_time).toLocaleString('zh-CN')
                        : '-'}
                    </td>
                    <td className="task-time-cell">
                      {task.last_run_time
                        ? new Date(task.last_run_time).toLocaleString('zh-CN')
                        : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="pagination">
            <button
              className="page-btn"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              上一页
            </button>
            <span className="page-info">
              第 {page} / {totalPages} 页
            </span>
            <button
              className="page-btn"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              下一页
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
