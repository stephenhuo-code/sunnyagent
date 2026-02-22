/**
 * Admin panel with sidebar navigation for different admin sections
 */

import { useState } from "react";
import { Users, Settings, Clock } from "lucide-react";
import { UserManagement } from "./UserManagement";
import { SystemSettings } from "./SystemSettings";
import { ScheduledTasks } from "./ScheduledTasks";
import "./Admin.css";

type AdminTab = "users" | "scheduled-tasks" | "settings";

export function AdminPanel() {
  const [activeTab, setActiveTab] = useState<AdminTab>("users");

  return (
    <div className="admin-panel">
      <div className="admin-sidebar">
        <div className="admin-sidebar-header">
          <h2>管理面板</h2>
        </div>
        <nav className="admin-nav">
          <button
            className={`admin-nav-item ${activeTab === "users" ? "active" : ""}`}
            onClick={() => setActiveTab("users")}
          >
            <Users size={18} />
            <span>用户管理</span>
          </button>
          <button
            className={`admin-nav-item ${activeTab === "scheduled-tasks" ? "active" : ""}`}
            onClick={() => setActiveTab("scheduled-tasks")}
          >
            <Clock size={18} />
            <span>定时任务</span>
          </button>
          <button
            className={`admin-nav-item ${activeTab === "settings" ? "active" : ""}`}
            onClick={() => setActiveTab("settings")}
          >
            <Settings size={18} />
            <span>系统设置</span>
          </button>
        </nav>
      </div>

      <div className="admin-content">
        {activeTab === "users" && <UserManagement />}
        {activeTab === "scheduled-tasks" && <ScheduledTasks />}
        {activeTab === "settings" && <SystemSettings />}
      </div>
    </div>
  );
}
