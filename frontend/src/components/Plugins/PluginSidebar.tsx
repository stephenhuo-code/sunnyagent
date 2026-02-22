/**
 * Plugin sidebar component - displays list of plugins with filtering.
 */

import { useState, useMemo, useRef, useEffect } from "react";
import { Plus, Search, Upload, ChevronDown, ChevronRight } from "lucide-react";
import type { PluginInfo, PluginSource, PluginType } from "../../types/plugins";
import "./Plugins.css";

interface PluginSidebarProps {
  plugins: PluginInfo[];
  selectedPlugin: PluginInfo | null;
  onSelectPlugin: (plugin: PluginInfo) => void;
  onAddClick: (action?: "browse" | "upload") => void;
  loading?: boolean;
}

// Exclude preset from user-configurable sources
type FilterSource = Exclude<PluginSource, "preset"> | "all";
type FilterType = PluginType | "all";

export function PluginSidebar({
  plugins,
  selectedPlugin,
  onSelectPlugin,
  onAddClick,
  loading = false,
}: PluginSidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<FilterSource>("all");
  const [typeFilter, setTypeFilter] = useState<FilterType>("all");
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());
  const addMenuRef = useRef<HTMLDivElement>(null);

  // Toggle agent expansion
  const toggleAgentExpand = (agentName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(agentName)) {
        next.delete(agentName);
      } else {
        next.add(agentName);
      }
      return next;
    });
  };

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (addMenuRef.current && !addMenuRef.current.contains(e.target as Node)) {
        setShowAddMenu(false);
      }
    };
    if (showAddMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showAddMenu]);

  // Filter plugins based on search and filters (exclude preset/built-in plugins)
  const filteredPlugins = useMemo(() => {
    return plugins.filter((plugin) => {
      // Always exclude preset (built-in) plugins - they're not user-configurable
      if (plugin.source === "preset") {
        return false;
      }

      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const matchesSearch =
          plugin.name.toLowerCase().includes(query) ||
          plugin.display_name.toLowerCase().includes(query) ||
          plugin.description.toLowerCase().includes(query);
        if (!matchesSearch) return false;
      }

      // Source filter
      if (sourceFilter !== "all" && plugin.source !== sourceFilter) {
        return false;
      }

      // Type filter
      if (typeFilter !== "all" && plugin.type !== typeFilter) {
        return false;
      }

      return true;
    });
  }, [plugins, searchQuery, sourceFilter, typeFilter]);

  // Group plugins by source (excluding preset)
  // For package source, only include agents (skills are nested under agents)
  const groupedPlugins = useMemo(() => {
    const groups: Record<string, PluginInfo[]> = {
      package: [],
      uploaded: [],
      shared: [],
    };

    filteredPlugins.forEach((plugin) => {
      // For package plugins, only add agents to the top level
      // Skills are already nested in agent.skills
      if (plugin.source === "package") {
        if (plugin.type === "agent") {
          groups.package.push(plugin);
        }
        // Skip standalone package skills - they should be shown under their agent
      } else {
        groups[plugin.source].push(plugin);
      }
    });

    return groups;
  }, [filteredPlugins]);

  const getSourceLabel = (source: string): string => {
    const labels: Record<string, string> = {
      package: "Packages",
      uploaded: "Uploaded",
      shared: "Shared",
    };
    return labels[source] || source;
  };

  const getPluginIcon = (plugin: PluginInfo): string => {
    if (plugin.type === "agent") {
      return "🤖";
    }
    if (plugin.skill_type === "workflow") {
      return "🔄";
    }
    return "⚡";
  };

  return (
    <div className="plugin-sidebar">
      <div className="plugin-sidebar-header">
        <h2>Plugins</h2>
        <div className="plugin-add-wrapper" ref={addMenuRef}>
          <button
            className="plugin-add-button"
            onClick={() => setShowAddMenu(!showAddMenu)}
            title="Add plugin"
          >
            <Plus size={16} />
          </button>
          {showAddMenu && (
            <div className="plugin-add-menu">
              <button
                className="plugin-add-menu-item"
                onClick={() => {
                  setShowAddMenu(false);
                  onAddClick("browse");
                }}
              >
                <Search size={14} />
                <span>Browse plugins</span>
              </button>
              <button
                className="plugin-add-menu-item"
                onClick={() => {
                  setShowAddMenu(false);
                  onAddClick("upload");
                }}
              >
                <Upload size={14} />
                <span>Upload plugin</span>
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="plugin-search">
        <input
          type="text"
          placeholder="Search plugins..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="plugin-search-input"
        />
      </div>

      <div className="plugin-filters">
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value as FilterSource)}
          className="plugin-filter-select"
        >
          <option value="all">All Sources</option>
          <option value="package">Packages</option>
          <option value="uploaded">Uploaded</option>
          <option value="shared">Shared</option>
        </select>

        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as FilterType)}
          className="plugin-filter-select"
        >
          <option value="all">All Types</option>
          <option value="agent">Agents</option>
          <option value="skill">Skills</option>
        </select>
      </div>

      <div className="plugin-list">
        {loading ? (
          <div className="plugin-loading">Loading plugins...</div>
        ) : filteredPlugins.length === 0 ? (
          <div className="plugin-empty">No plugins found</div>
        ) : (
          Object.entries(groupedPlugins).map(
            ([source, sourcePlugins]) =>
              sourcePlugins.length > 0 && (
                <div key={source} className="plugin-group">
                  <div className="plugin-group-header">{getSourceLabel(source)}</div>
                  {sourcePlugins.map((plugin) => (
                    <div key={plugin.name} className="plugin-tree-item">
                      {/* Plugin item */}
                      <div
                        className={`plugin-item ${selectedPlugin?.name === plugin.name ? "selected" : ""} ${!plugin.enabled ? "disabled" : ""}`}
                        onClick={() => onSelectPlugin(plugin)}
                      >
                        {/* Expand/collapse button for package agents with skills */}
                        {source === "package" && plugin.type === "agent" && plugin.skills && plugin.skills.length > 0 ? (
                          <button
                            className="plugin-expand-btn"
                            onClick={(e) => toggleAgentExpand(plugin.name, e)}
                          >
                            {expandedAgents.has(plugin.name) ? (
                              <ChevronDown size={14} />
                            ) : (
                              <ChevronRight size={14} />
                            )}
                          </button>
                        ) : (
                          <span className="plugin-expand-spacer" />
                        )}
                        <span className="plugin-icon">{getPluginIcon(plugin)}</span>
                        <div className="plugin-item-content">
                          <div className="plugin-item-name">{plugin.display_name}</div>
                          <div className="plugin-item-type">
                            {plugin.type}
                            {plugin.skill_type === "workflow" && " (workflow)"}
                            {plugin.skills && plugin.skills.length > 0 && ` (${plugin.skills.length} skills)`}
                          </div>
                        </div>
                        <div
                          className={`plugin-status ${plugin.enabled ? "enabled" : "disabled"}`}
                        />
                      </div>

                      {/* Nested skills for package agents */}
                      {source === "package" &&
                        plugin.type === "agent" &&
                        plugin.skills &&
                        plugin.skills.length > 0 &&
                        expandedAgents.has(plugin.name) && (
                          <div className="plugin-nested-skills">
                            {plugin.skills.map((skill) => (
                              <div
                                key={skill.name}
                                className={`plugin-item plugin-skill-item ${selectedPlugin?.name === skill.name ? "selected" : ""} ${!skill.enabled ? "disabled" : ""}`}
                                onClick={() => onSelectPlugin(skill)}
                              >
                                <span className="plugin-expand-spacer" />
                                <span className="plugin-icon">{getPluginIcon(skill)}</span>
                                <div className="plugin-item-content">
                                  <div className="plugin-item-name">{skill.display_name}</div>
                                  <div className="plugin-item-type">
                                    skill
                                    {skill.skill_type === "workflow" && " (workflow)"}
                                  </div>
                                </div>
                                <div
                                  className={`plugin-status ${skill.enabled ? "enabled" : "disabled"}`}
                                />
                              </div>
                            ))}
                          </div>
                        )}
                    </div>
                  ))}
                </div>
              )
          )
        )}
      </div>
    </div>
  );
}
