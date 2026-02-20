/**
 * Main layout with sidebar and content area
 */

import { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import type { ConversationSummary } from '../../api/conversations';
import type { ProjectSummary } from '../../api/projects';
import './Layout.css';

interface MainLayoutProps {
  children: ReactNode;
  conversationList?: ReactNode | ((collapsed: boolean) => ReactNode);
  projectsSection?: ReactNode | ((collapsed: boolean) => ReactNode);
  onNewConversation: () => void;
  onShowAdmin?: () => void;
  // Props for conversation popover
  conversations?: ConversationSummary[];
  conversationsLoading?: boolean;
  conversationsError?: string | null;
  selectedConversationId?: string | null;
  onSelectConversation?: (id: string) => void;
  onUpdateConversation?: (id: string, title: string) => Promise<void>;
  onDeleteConversation?: (id: string) => Promise<void>;
  onCreateProject?: () => void;
  // Props for project popover
  projects?: ProjectSummary[];
  projectsLoading?: boolean;
  projectsError?: string | null;
  selectedProjectId?: string | null;
  onSelectProject?: (id: string) => void;
}

export function MainLayout({
  children,
  conversationList,
  projectsSection,
  onNewConversation,
  onShowAdmin,
  conversations,
  conversationsLoading,
  conversationsError,
  selectedConversationId,
  onSelectConversation,
  onUpdateConversation,
  onDeleteConversation,
  onCreateProject,
  projects,
  projectsLoading,
  projectsError,
  selectedProjectId,
  onSelectProject,
}: MainLayoutProps) {
  return (
    <div className="main-layout">
      <Sidebar
        onNewConversation={onNewConversation}
        onAdminClick={onShowAdmin}
        conversations={conversations}
        conversationsLoading={conversationsLoading}
        conversationsError={conversationsError}
        selectedConversationId={selectedConversationId}
        onSelectConversation={onSelectConversation}
        onUpdateConversation={onUpdateConversation}
        onDeleteConversation={onDeleteConversation}
        projectsSection={projectsSection}
        onCreateProject={onCreateProject}
        projects={projects}
        projectsLoading={projectsLoading}
        projectsError={projectsError}
        selectedProjectId={selectedProjectId}
        onSelectProject={onSelectProject}
      >
        {conversationList}
      </Sidebar>
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
