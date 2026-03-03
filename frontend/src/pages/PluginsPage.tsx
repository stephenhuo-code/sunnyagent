/**
 * Plugins management page - integrates sidebar, middle panel and detail panel.
 */

import { useState, useEffect, useCallback } from "react";
import { PluginSidebar } from "../components/Plugins/PluginSidebar";
import { PluginMiddlePanel } from "../components/Plugins/PluginMiddlePanel";
import { PluginDetail } from "../components/Plugins/PluginDetail";
import { BrowsePluginsModal } from "../components/Plugins/BrowsePluginsModal";
import { UploadPluginModal } from "../components/Plugins/UploadPluginModal";
import type { CommandDetail, PluginInfo } from "../types/plugins";
import {
  listPlugins,
  updatePluginState,
  ratePlugin,
  deletePlugin,
  sharePlugin,
  getCommandDetail,
} from "../api/plugins";
import "../components/Plugins/Plugins.css";

export function PluginsPage() {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [selectedPlugin, setSelectedPlugin] = useState<PluginInfo | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<"commands" | "skills" | null>(null);
  const [selectedItem, setSelectedItem] = useState<string | null>(null);
  const [commandDetail, setCommandDetail] = useState<CommandDetail | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<PluginInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showBrowseModal, setShowBrowseModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);

  // Load plugins on mount
  const loadPlugins = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listPlugins();
      setPlugins(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load plugins");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPlugins();
  }, [loadPlugins]);

  // Handle plugin selection (clicking on the agent itself)
  const handleSelectPlugin = (plugin: PluginInfo) => {
    setSelectedPlugin(plugin);
    setSelectedCategory(null);
    setSelectedItem(null);
    setCommandDetail(null);
    setSelectedSkill(null);
  };

  // Handle category selection (Commands or Skills)
  const handleSelectCategory = (plugin: PluginInfo, category: "commands" | "skills") => {
    setSelectedPlugin(plugin);
    setSelectedCategory(category);
    setSelectedItem(null);
    setCommandDetail(null);
    setSelectedSkill(null);
  };

  // Handle command selection in middle panel
  const handleSelectCommand = async (name: string) => {
    setSelectedItem(name);
    setSelectedSkill(null);
    setDetailLoading(true);
    try {
      const detail = await getCommandDetail(name);
      setCommandDetail(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load command details");
      setCommandDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  // Handle skill selection in middle panel
  const handleSelectSkillItem = (skill: PluginInfo) => {
    setSelectedItem(skill.name);
    setCommandDetail(null);
    setSelectedSkill(skill);
  };

  // Handle enable/disable toggle
  const handleToggleEnabled = async (plugin: PluginInfo, enabled: boolean) => {
    try {
      setDetailLoading(true);
      const updated = await updatePluginState(plugin.name, { enabled });
      // Update local state with full backend response (includes updated nested skills)
      setPlugins((prev) =>
        prev.map((p) => (p.name === plugin.name ? updated : p))
      );
      if (selectedPlugin?.name === plugin.name) {
        setSelectedPlugin(updated);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update plugin state");
    } finally {
      setDetailLoading(false);
    }
  };

  // Handle rating
  const handleRate = async (plugin: PluginInfo, rating: number) => {
    try {
      setDetailLoading(true);
      const ratingInfo = await ratePlugin(plugin.name, { rating });
      // Update local state
      setPlugins((prev) =>
        prev.map((p) => (p.name === plugin.name ? { ...p, rating: ratingInfo } : p))
      );
      if (selectedPlugin?.name === plugin.name) {
        setSelectedPlugin({ ...selectedPlugin, rating: ratingInfo });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rate plugin");
    } finally {
      setDetailLoading(false);
    }
  };

  // Handle share
  const handleShare = async (plugin: PluginInfo) => {
    if (!confirm(`Share "${plugin.display_name}" to the marketplace?`)) {
      return;
    }
    try {
      setDetailLoading(true);
      await sharePlugin(plugin.name);
      await loadPlugins(); // Reload to get updated state
      if (selectedPlugin?.name === plugin.name) {
        setSelectedPlugin(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to share plugin");
    } finally {
      setDetailLoading(false);
    }
  };

  // Handle delete
  const handleDelete = async (plugin: PluginInfo) => {
    if (!confirm(`Delete "${plugin.display_name}"? This action cannot be undone.`)) {
      return;
    }
    try {
      setDetailLoading(true);
      await deletePlugin(plugin.name);
      await loadPlugins(); // Reload to get updated list
      if (selectedPlugin?.name === plugin.name) {
        setSelectedPlugin(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete plugin");
    } finally {
      setDetailLoading(false);
    }
  };

  // Handle add click - now accepts optional action type
  const handleAddClick = (action?: "browse" | "upload") => {
    if (action === "upload") {
      setShowUploadModal(true);
    } else {
      setShowBrowseModal(true);
    }
  };

  // Handle modal close
  const handleCloseBrowseModal = () => {
    setShowBrowseModal(false);
    loadPlugins(); // Reload in case user enabled something
  };

  // Handle upload modal close
  const handleCloseUploadModal = () => {
    setShowUploadModal(false);
  };

  // Handle upload success
  const handleUploadSuccess = () => {
    loadPlugins();
  };

  // Determine if we should show three-column layout
  const showMiddlePanel = selectedPlugin && selectedCategory;

  return (
    <div className="plugins-page">
      {error && (
        <div className="plugins-error">
          <span>{error}</span>
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      <div className={`plugins-layout ${showMiddlePanel ? "three-columns" : ""}`}>
        <PluginSidebar
          plugins={plugins}
          selectedPlugin={selectedPlugin}
          selectedCategory={selectedCategory}
          onSelectPlugin={handleSelectPlugin}
          onSelectCategory={handleSelectCategory}
          onAddClick={handleAddClick}
          loading={loading}
        />

        {showMiddlePanel && (
          <PluginMiddlePanel
            plugin={selectedPlugin}
            category={selectedCategory}
            selectedItem={selectedItem}
            onSelectCommand={handleSelectCommand}
            onSelectSkill={handleSelectSkillItem}
          />
        )}

        <PluginDetail
          plugin={selectedSkill || (selectedCategory ? null : selectedPlugin)}
          commandDetail={commandDetail}
          onToggleEnabled={handleToggleEnabled}
          onShare={handleShare}
          onDelete={handleDelete}
          onRate={handleRate}
          loading={detailLoading}
        />
      </div>

      {showBrowseModal && (
        <BrowsePluginsModal
          onClose={handleCloseBrowseModal}
          onPluginEnabled={loadPlugins}
        />
      )}

      {showUploadModal && (
        <UploadPluginModal
          onClose={handleCloseUploadModal}
          onUploadSuccess={handleUploadSuccess}
        />
      )}
    </div>
  );
}
