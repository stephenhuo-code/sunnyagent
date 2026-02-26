/**
 * Plugin detail panel - displays full plugin information and controls.
 */

import ReactMarkdown from "react-markdown";
import type { CommandDetail, PluginInfo } from "../../types/plugins";
import "./Plugins.css";

interface PluginDetailProps {
  plugin: PluginInfo | null;
  commandDetail: CommandDetail | null;
  onToggleEnabled?: (plugin: PluginInfo, enabled: boolean) => void;
  onShare?: (plugin: PluginInfo) => void;
  onDelete?: (plugin: PluginInfo) => void;
  onRate?: (plugin: PluginInfo, rating: number) => void;
  loading?: boolean;
}

export function PluginDetail({
  plugin,
  commandDetail,
  onToggleEnabled,
  onShare,
  onDelete,
  onRate,
  loading = false,
}: PluginDetailProps) {
  // Show command detail if available
  if (commandDetail) {
    return (
      <div className="plugin-detail">
        {loading && <div className="plugin-detail-loading">Loading...</div>}

        <div className="plugin-detail-header">
          <div className="plugin-detail-title">
            <h2>/{commandDetail.name}</h2>
            <span className="plugin-badge type-command">Command</span>
          </div>
        </div>

        <div className="plugin-detail-section">
          <h3>Description</h3>
          <p>{commandDetail.description}</p>
        </div>

        {commandDetail.argument_hint && (
          <div className="plugin-detail-section">
            <h3>Usage</h3>
            <code className="command-usage">
              /{commandDetail.name} {commandDetail.argument_hint}
            </code>
          </div>
        )}

        <div className="plugin-detail-section command-workflow">
          <h3>Workflow</h3>
          <div className="command-content">
            <ReactMarkdown>{commandDetail.content}</ReactMarkdown>
          </div>
        </div>
      </div>
    );
  }

  if (!plugin) {
    return (
      <div className="plugin-detail plugin-detail-empty">
        <div className="plugin-detail-placeholder">
          <span className="placeholder-icon">{"\u{1F50C}"}</span>
          <p>Select a plugin to view details</p>
        </div>
      </div>
    );
  }

  const getTypeLabel = (): string => {
    if (plugin.type === "agent") {
      return "Agent";
    }
    return "Skill";
  };

  const getSourceLabel = (): string => {
    const labels: Record<string, string> = {
      preset: "Built-in",
      package: "Package",
      uploaded: "Uploaded",
      shared: "Shared",
    };
    return labels[plugin.source] || plugin.source;
  };

  const canRate = plugin.source === "package" || plugin.source === "shared";
  const canShare = plugin.source === "uploaded" && !plugin.is_delisted;
  const canDelete = plugin.source === "uploaded" && !plugin.is_delisted;

  const renderRating = () => {
    if (!plugin.rating) return null;

    const stars = [];
    for (let i = 1; i <= 5; i++) {
      stars.push(
        <span
          key={i}
          className={`rating-star ${i <= Math.round(plugin.rating.average) ? "filled" : ""}`}
          onClick={() => canRate && onRate?.(plugin, i)}
          style={{ cursor: canRate ? "pointer" : "default" }}
        >
          ★
        </span>
      );
    }

    return (
      <div className="plugin-rating">
        <div className="rating-stars">{stars}</div>
        <span className="rating-info">
          {plugin.rating.average.toFixed(1)} ({plugin.rating.count} reviews)
        </span>
      </div>
    );
  };

  return (
    <div className="plugin-detail">
      {loading && <div className="plugin-detail-loading">Updating...</div>}

      <div className="plugin-detail-header">
        <div className="plugin-detail-title">
          <h2>{plugin.display_name}</h2>
          <span className={`plugin-badge source-${plugin.source}`}>{getSourceLabel()}</span>
          <span className={`plugin-badge type-${plugin.type}`}>{getTypeLabel()}</span>
        </div>

        <div className="plugin-toggle">
          <label className="toggle-switch">
            <input
              type="checkbox"
              checked={plugin.enabled}
              onChange={(e) => onToggleEnabled?.(plugin, e.target.checked)}
            />
            <span className="toggle-slider" />
          </label>
          <span className="toggle-label">{plugin.enabled ? "Enabled" : "Disabled"}</span>
        </div>
      </div>

      {renderRating()}

      <div className="plugin-detail-section">
        <h3>Description</h3>
        <p>{plugin.description || "No description available."}</p>
      </div>

      <div className="plugin-detail-meta">
        <div className="meta-item">
          <span className="meta-label">Version</span>
          <span className="meta-value">{plugin.version}</span>
        </div>
        {plugin.author && (
          <div className="meta-item">
            <span className="meta-label">Author</span>
            <span className="meta-value">{plugin.author}</span>
          </div>
        )}
        {plugin.uploader_name && (
          <div className="meta-item">
            <span className="meta-label">Uploaded by</span>
            <span className="meta-value">{plugin.uploader_name}</span>
          </div>
        )}
      </div>

      {plugin.capabilities && plugin.capabilities.length > 0 && (
        <div className="plugin-detail-section">
          <h3>Capabilities</h3>
          <div className="plugin-tags">
            {plugin.capabilities.map((cap) => (
              <span key={cap} className="plugin-tag">
                {cap}
              </span>
            ))}
          </div>
        </div>
      )}

      {plugin.commands && plugin.commands.length > 0 && (
        <div className="plugin-detail-section">
          <h3>Commands</h3>
          <div className="plugin-commands">
            {plugin.commands.map((cmd) => (
              <code key={cmd} className="plugin-command">
                /{cmd}
              </code>
            ))}
          </div>
        </div>
      )}

      {plugin.skills && plugin.skills.length > 0 && (
        <div className="plugin-detail-section">
          <h3>Skills</h3>
          <ul className="plugin-skills-list">
            {plugin.skills.map((skill) => (
              <li key={skill.name}>
                <strong>{skill.display_name}</strong>
                <p>{skill.description}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {plugin.is_delisted && (
        <div className="plugin-delisted-warning">
          This plugin has been delisted by its owner but remains available to existing users.
        </div>
      )}

      <div className="plugin-detail-actions">
        {canShare && (
          <button className="plugin-action-button share" onClick={() => onShare?.(plugin)}>
            Share to Marketplace
          </button>
        )}
        {canDelete && (
          <button className="plugin-action-button delete" onClick={() => onDelete?.(plugin)}>
            Delete Plugin
          </button>
        )}
      </div>
    </div>
  );
}
