/**
 * System settings panel for administrators
 */

import { useState, useEffect, useCallback } from "react";
import {
  Settings,
  ExternalLink,
  Loader2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  BarChart3,
} from "lucide-react";
import {
  getLangfuseStatus,
  getUsageStats,
  type LangfuseStatus,
  type UsageStats,
} from "../../api/system";
import "./Admin.css";

const TIME_RANGE_OPTIONS = [
  { value: 1, label: "1 天" },
  { value: 7, label: "7 天" },
  { value: 30, label: "30 天" },
];

function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(2) + "M";
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + "K";
  }
  return num.toLocaleString();
}

function formatCost(cost: number): string {
  if (cost === 0) return "$0.00";
  if (cost < 0.01) return "<$0.01";
  return `$${cost.toFixed(2)}`;
}

export function SystemSettings() {
  const [langfuse, setLangfuse] = useState<LangfuseStatus | null>(null);
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingUsage, setIsLoadingUsage] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [startDate, setStartDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );

  const loadStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const status = await getLangfuseStatus();
      setLangfuse(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载系统状态失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadUsageStats = useCallback(async () => {
    setIsLoadingUsage(true);
    try {
      const stats = await getUsageStats("day", days, startDate || undefined);
      setUsageStats(stats);
    } catch (err) {
      console.error("Failed to load usage stats:", err);
    } finally {
      setIsLoadingUsage(false);
    }
  }, [days, startDate]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (langfuse?.enabled) {
      loadUsageStats();
    }
  }, [langfuse?.enabled, loadUsageStats]);

  const openLangfuse = () => {
    if (langfuse?.url) {
      window.open(langfuse.url, "_blank", "noopener,noreferrer");
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "healthy":
        return <CheckCircle2 size={18} className="status-icon healthy" />;
      case "unhealthy":
        return <XCircle size={18} className="status-icon unhealthy" />;
      case "disabled":
        return <AlertCircle size={18} className="status-icon disabled" />;
      default:
        return <AlertCircle size={18} className="status-icon" />;
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case "healthy":
        return "运行正常";
      case "unhealthy":
        return "连接异常";
      case "disabled":
        return "未启用";
      default:
        return "未知";
    }
  };

  // Calculate max value for bar chart scaling
  const maxTokens = usageStats?.by_time.length
    ? Math.max(...usageStats.by_time.map((t) => t.tokens))
    : 0;

  if (isLoading) {
    return (
      <div className="admin-loading">
        <Loader2 size={32} className="spin" />
        <span>加载系统设置...</span>
      </div>
    );
  }

  return (
    <div className="system-settings">
      <div className="admin-header">
        <div className="admin-title">
          <Settings size={24} />
          <h1>系统设置</h1>
        </div>
      </div>

      {error && (
        <div className="admin-error">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      <div className="settings-section">
        <h2>可观测性</h2>

        <div className="setting-card">
          <div className="setting-info">
            <h3>Langfuse</h3>
            <p>Agent 执行链路追踪与监控平台</p>
            {langfuse && (
              <>
                <div className="setting-status">
                  {getStatusIcon(langfuse.status)}
                  <span className={`status-text ${langfuse.status}`}>
                    {getStatusText(langfuse.status)}
                  </span>
                </div>
                {langfuse.enabled && langfuse.status === "healthy" && (
                  <button className="langfuse-link" onClick={openLangfuse}>
                    <ExternalLink size={14} />
                    <span>打开 Langfuse 控制台</span>
                  </button>
                )}
              </>
            )}
          </div>

          <div className="setting-actions">
            {langfuse?.enabled && langfuse.status === "unhealthy" && (
              <span className="warning-text">
                Langfuse 服务异常，请检查配置
              </span>
            )}
            {!langfuse?.enabled && (
              <span className="info-text">
                需要配置 LANGFUSE_PUBLIC_KEY 和 LANGFUSE_SECRET_KEY
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Token Usage Statistics Section */}
      {langfuse?.enabled && (
        <div className="settings-section">
          <div className="usage-section-header">
            <h2>Token 用量统计</h2>
            <button
              className="btn-secondary btn-small"
              onClick={loadUsageStats}
              disabled={isLoadingUsage}
            >
              {isLoadingUsage ? (
                <Loader2 size={16} className="spin" />
              ) : (
                <RefreshCw size={16} />
              )}
              刷新
            </button>
          </div>

          {/* Filters */}
          <div className="usage-filters">
            <div className="filter-group">
              <span className="filter-label">时间范围:</span>
              <select
                className="filter-select"
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
              >
                {TIME_RANGE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="filter-group">
              <span className="filter-label">起始日期:</span>
              <input
                type="date"
                className="filter-input"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
          </div>

          {/* Summary Cards */}
          {usageStats && (
            <>
              <div className="usage-summary">
                <div className="usage-card">
                  <div className="usage-card-icon">
                    <BarChart3 size={20} />
                  </div>
                  <div className="usage-card-content">
                    <div className="usage-card-value">
                      {formatNumber(usageStats.total_calls)}
                    </div>
                    <div className="usage-card-label">总调用次数</div>
                  </div>
                </div>
                <div className="usage-card">
                  <div className="usage-card-icon tokens">
                    <BarChart3 size={20} />
                  </div>
                  <div className="usage-card-content">
                    <div className="usage-card-value">
                      {formatNumber(usageStats.total_tokens)}
                    </div>
                    <div className="usage-card-label">总 Token 数</div>
                    <div className="usage-card-detail">
                      输入: {formatNumber(usageStats.input_tokens)} / 输出:{" "}
                      {formatNumber(usageStats.output_tokens)}
                    </div>
                  </div>
                </div>
                <div className="usage-card">
                  <div className="usage-card-icon cost">
                    <BarChart3 size={20} />
                  </div>
                  <div className="usage-card-content">
                    <div className="usage-card-value">
                      {formatCost(usageStats.total_cost_usd)}
                    </div>
                    <div className="usage-card-label">预估费用</div>
                  </div>
                </div>
              </div>

              {/* Trend Chart */}
              {usageStats.by_time.length > 0 && (
                <div className="usage-chart-section">
                  <h3>趋势图（按时间）</h3>
                  <div className="usage-chart-wrapper">
                    <div className="chart-y-unit">Token</div>
                    <div className="chart-y-axis">
                      <span className="y-axis-label">{formatNumber(maxTokens)}</span>
                      <span className="y-axis-label">{formatNumber(maxTokens / 2)}</span>
                      <span className="y-axis-label">0</span>
                    </div>
                    <div className="usage-chart">
                      {usageStats.by_time
                        .slice()
                        .reverse()
                        .map((item) => (
                          <div key={item.date} className="chart-bar-container">
                            <div
                              className="chart-bar"
                              style={{
                                height: `${
                                  maxTokens > 0
                                    ? (item.tokens / maxTokens) * 100
                                    : 0
                                }%`,
                              }}
                              title={`${item.date}: ${formatNumber(
                                item.tokens
                              )} tokens, ${item.calls} 次调用`}
                            />
                            <div className="chart-bar-label">
                              {item.date.slice(5)}
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                </div>
              )}

              {/* By Model Table */}
              {usageStats.by_model.length > 0 && (
                <div className="usage-table-section">
                  <h3>按模型分布</h3>
                  <div className="usage-table-container">
                    <table className="usage-table">
                      <thead>
                        <tr>
                          <th>模型</th>
                          <th>Token 数</th>
                          <th>费用</th>
                          <th>调用数</th>
                        </tr>
                      </thead>
                      <tbody>
                        {usageStats.by_model.map((item) => (
                          <tr key={item.model}>
                            <td className="model-name">{item.model}</td>
                            <td>{formatNumber(item.tokens)}</td>
                            <td>{formatCost(item.cost)}</td>
                            <td>{item.calls}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* By User Table */}
              {usageStats.by_user.length > 0 && (
                <div className="usage-table-section">
                  <h3>按用户分布</h3>
                  <div className="usage-table-container">
                    <table className="usage-table">
                      <thead>
                        <tr>
                          <th>用户</th>
                          <th>Token 数</th>
                          <th>费用</th>
                          <th>调用数</th>
                        </tr>
                      </thead>
                      <tbody>
                        {usageStats.by_user.map((item) => (
                          <tr key={item.user_id}>
                            <td className="user-name">{item.username}</td>
                            <td>{formatNumber(item.tokens)}</td>
                            <td>{formatCost(item.cost)}</td>
                            <td>{item.calls}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* No data message */}
              {usageStats.total_calls === 0 && (
                <div className="usage-empty">
                  <BarChart3 size={48} />
                  <p>暂无用量数据</p>
                  <span>开始使用对话功能后，这里会显示统计信息</span>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
