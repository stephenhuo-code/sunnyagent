/**
 * Plugin middle panel - displays list of commands or skills based on selected category.
 */

import type { PluginInfo } from "../../types/plugins";
import "./Plugins.css";

interface PluginMiddlePanelProps {
  plugin: PluginInfo;
  category: "commands" | "skills";
  selectedItem: string | null; // command name or skill name
  onSelectCommand: (name: string) => void;
  onSelectSkill: (skill: PluginInfo) => void;
}

export function PluginMiddlePanel({
  plugin,
  category,
  selectedItem,
  onSelectCommand,
  onSelectSkill,
}: PluginMiddlePanelProps) {
  const getSkillIcon = (skill: PluginInfo): string => {
    if (skill.skill_type === "workflow") {
      return "\u{1F504}"; // Workflow icon
    }
    return "\u26A1"; // Lightning bolt for atomic skills
  };

  return (
    <div className="plugin-middle-panel">
      <div className="middle-panel-header">
        <h3>{category === "commands" ? "Commands" : "Skills"}</h3>
        <span className="middle-panel-count">
          {category === "commands"
            ? plugin.commands?.length || 0
            : plugin.skills?.length || 0}
        </span>
      </div>
      <div className="middle-panel-list">
        {category === "commands" &&
          plugin.commands?.map((cmd) => (
            <div
              key={cmd}
              className={`middle-panel-item ${selectedItem === cmd ? "selected" : ""}`}
              onClick={() => onSelectCommand(cmd)}
            >
              <span className="item-icon">{"\u2318"}</span>
              <div className="item-content">
                <span className="item-name">/{cmd}</span>
              </div>
            </div>
          ))}
        {category === "skills" &&
          plugin.skills?.map((skill) => (
            <div
              key={skill.name}
              className={`middle-panel-item ${selectedItem === skill.name ? "selected" : ""}`}
              onClick={() => onSelectSkill(skill)}
            >
              <span className="item-icon">{getSkillIcon(skill)}</span>
              <div className="item-content">
                <span className="item-name">{skill.display_name}</span>
                {skill.skill_type === "workflow" && (
                  <span className="item-badge">workflow</span>
                )}
              </div>
            </div>
          ))}
        {category === "commands" && (!plugin.commands || plugin.commands.length === 0) && (
          <div className="middle-panel-empty">No commands available</div>
        )}
        {category === "skills" && (!plugin.skills || plugin.skills.length === 0) && (
          <div className="middle-panel-empty">No skills available</div>
        )}
      </div>
    </div>
  );
}
