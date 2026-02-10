/**
 * Sidebar header with logo and collapse button
 */

import { PanelLeftClose } from 'lucide-react';
import './Layout.css';

interface SidebarHeaderProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function SidebarHeader({ collapsed, onToggle }: SidebarHeaderProps) {
  return (
    <div className="sidebar-header">
      <div
        className="sidebar-logo"
        onClick={collapsed ? onToggle : undefined}
        style={collapsed ? { cursor: 'pointer' } : undefined}
        title={collapsed ? '展开' : undefined}
      >
        <svg width="24" height="24" viewBox="0 0 48 48" fill="none">
          {/* Sun rays */}
          <g stroke="currentColor" strokeWidth="3" strokeLinecap="round">
            <line x1="24" y1="4" x2="24" y2="10" />
            <line x1="24" y1="38" x2="24" y2="44" />
            <line x1="4" y1="24" x2="10" y2="24" />
            <line x1="38" y1="24" x2="44" y2="24" />
            <line x1="9.86" y1="9.86" x2="14.1" y2="14.1" />
            <line x1="33.9" y1="33.9" x2="38.14" y2="38.14" />
            <line x1="9.86" y1="38.14" x2="14.1" y2="33.9" />
            <line x1="33.9" y1="14.1" x2="38.14" y2="9.86" />
          </g>
          {/* Central circle */}
          <circle cx="24" cy="24" r="12" fill="currentColor" opacity="0.15" />
          <circle cx="24" cy="24" r="12" stroke="currentColor" strokeWidth="3" fill="none" />
          {/* AI nodes */}
          <circle cx="24" cy="21" r="2.5" fill="currentColor" />
          <circle cx="19" cy="26" r="2" fill="currentColor" />
          <circle cx="29" cy="26" r="2" fill="currentColor" />
          <path d="M24 23.5v2M21.5 25l-1.5 1M26.5 25l1.5 1" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
        {!collapsed && <span>Sunny Agent</span>}
      </div>
      {!collapsed && (
        <button className="collapse-btn" onClick={onToggle} title="收起">
          <PanelLeftClose size={18} />
        </button>
      )}
    </div>
  );
}
