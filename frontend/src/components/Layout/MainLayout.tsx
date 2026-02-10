/**
 * Main layout with sidebar and content area
 */

import { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import type { ConversationSummary } from '../../api/conversations';
import './Layout.css';

interface MainLayoutProps {
  children: ReactNode;
  conversationList?: ReactNode | ((collapsed: boolean) => ReactNode);
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
}

export function MainLayout({
  children,
  conversationList,
  onNewConversation,
  onShowAdmin,
  conversations,
  conversationsLoading,
  conversationsError,
  selectedConversationId,
  onSelectConversation,
  onUpdateConversation,
  onDeleteConversation,
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
      >
        {conversationList}
      </Sidebar>
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
