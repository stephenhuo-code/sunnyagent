/**
 * Browse plugins modal - marketplace view for discovering plugins.
 */

import { useState, useEffect, useMemo } from "react";
import { X } from "lucide-react";
import type { PluginInfo, PluginSource } from "../../types/plugins";
import { browseMarketplace, updatePluginState } from "../../api/plugins";
import "./Plugins.css";

interface BrowsePluginsModalProps {
  onClose: () => void;
  onPluginEnabled?: () => void;
}

type TabSource = "all" | "preset" | "package" | "shared";

export function BrowsePluginsModal({ onClose, onPluginEnabled }: BrowsePluginsModalProps) {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabSource>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Load plugins
  useEffect(() => {
    const loadPlugins = async () => {
      try {
        setLoading(true);
        setError(null);

        const sourceFilter =
          activeTab === "all" ? undefined : (activeTab as Exclude<PluginSource, "uploaded">);
        const data = await browseMarketplace({ source: sourceFilter });
        setPlugins(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load plugins");
      } finally {
        setLoading(false);
      }
    };

    loadPlugins();
  }, [activeTab]);

  // Filter plugins by search
  const filteredPlugins = useMemo(() => {
    if (!searchQuery) return plugins;

    const query = searchQuery.toLowerCase();
    return plugins.filter(
      (p) =>
        p.name.toLowerCase().includes(query) ||
        p.display_name.toLowerCase().includes(query) ||
        p.description.toLowerCase().includes(query)
    );
  }, [plugins, searchQuery]);

  // Handle enable/manage click
  const handlePluginAction = async (plugin: PluginInfo) => {
    if (plugin.enabled) {
      // Already enabled, close modal to manage
      onClose();
      return;
    }

    try {
      await updatePluginState(plugin.name, { enabled: true });
      // Update local state
      setPlugins((prev) =>
        prev.map((p) => (p.name === plugin.name ? { ...p, enabled: true } : p))
      );
      onPluginEnabled?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to enable plugin");
    }
  };

  // Handle backdrop click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const renderPluginCard = (plugin: PluginInfo) => (
    <div key={plugin.name} className="browse-plugin-card" onClick={() => handlePluginAction(plugin)}>
      <div className="browse-plugin-card-header">
        <span className="browse-plugin-card-name">{plugin.display_name}</span>
        <span className="browse-plugin-card-type">
          {plugin.type}
          {plugin.skill_type === "workflow" && " (workflow)"}
        </span>
      </div>

      <p className="browse-plugin-card-description">{plugin.description || "No description"}</p>

      <div className="browse-plugin-card-footer">
        {plugin.rating ? (
          <span className="browse-plugin-card-rating">
            <span className="star">★</span>
            {plugin.rating.average.toFixed(1)}
            <span>({plugin.rating.count})</span>
          </span>
        ) : (
          <span />
        )}

        <button
          className={`browse-plugin-card-action ${plugin.enabled ? "manage" : "enable"}`}
          onClick={(e) => {
            e.stopPropagation();
            handlePluginAction(plugin);
          }}
        >
          {plugin.enabled ? "Manage" : "Enable"}
        </button>
      </div>
    </div>
  );

  return (
    <div className="browse-plugins-modal-overlay" onClick={handleBackdropClick}>
      <div className="browse-plugins-modal">
        <div className="browse-plugins-header">
          <h2>Browse Plugins</h2>
          <button className="browse-plugins-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="browse-plugins-tabs">
          <button
            className={`browse-plugins-tab ${activeTab === "all" ? "active" : ""}`}
            onClick={() => setActiveTab("all")}
          >
            All
          </button>
          <button
            className={`browse-plugins-tab ${activeTab === "preset" ? "active" : ""}`}
            onClick={() => setActiveTab("preset")}
          >
            Built-in
          </button>
          <button
            className={`browse-plugins-tab ${activeTab === "package" ? "active" : ""}`}
            onClick={() => setActiveTab("package")}
          >
            Packages
          </button>
          <button
            className={`browse-plugins-tab ${activeTab === "shared" ? "active" : ""}`}
            onClick={() => setActiveTab("shared")}
          >
            Shared
          </button>
        </div>

        <div className="browse-plugins-search">
          <input
            type="text"
            placeholder="Search plugins..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="browse-plugins-content">
          {error && <div className="plugins-error">{error}</div>}

          {loading ? (
            <div className="browse-plugins-loading">Loading plugins...</div>
          ) : filteredPlugins.length === 0 ? (
            <div className="browse-plugins-empty">
              {searchQuery ? "No plugins match your search" : "No plugins available"}
            </div>
          ) : (
            <div className="browse-plugins-grid">{filteredPlugins.map(renderPluginCard)}</div>
          )}
        </div>
      </div>
    </div>
  );
}
