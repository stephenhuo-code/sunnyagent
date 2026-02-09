import { useState, useCallback } from "react";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { useConversations } from "./hooks/useConversations";
import { LoginPage } from "./components/Auth/LoginPage";
import { MainLayout } from "./components/Layout/MainLayout";
import { ConversationList } from "./components/Conversations";
import { UserManagement } from "./components/Admin";
import ChatContainer from "./components/ChatContainer";
import { Loader2 } from "lucide-react";
import { getConversation } from "./api/conversations";

type View = "chat" | "admin";

function AppContent() {
  const { isAuthenticated, isLoading } = useAuth();
  const [currentView, setCurrentView] = useState<View>("chat");
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  const [chatKey, setChatKey] = useState(0);

  const conversations = useConversations();

  const handleNewConversation = useCallback(async () => {
    // Create a new conversation and select it
    try {
      const conv = await conversations.create();
      setCurrentThreadId(conv.thread_id);
      setChatKey((prev) => prev + 1);
      setCurrentView("chat");
    } catch (err) {
      console.error("Failed to create conversation:", err);
      // Fallback: just reset to a new chat without conversation
      setCurrentThreadId(null);
      setChatKey((prev) => prev + 1);
      setCurrentView("chat");
    }
  }, [conversations]);

  const handleSelectConversation = useCallback(async (id: string) => {
    try {
      const conv = await getConversation(id);
      conversations.select(id);
      setCurrentThreadId(conv.thread_id);
      setChatKey((prev) => prev + 1);
      setCurrentView("chat");
    } catch (err) {
      console.error("Failed to load conversation:", err);
    }
  }, [conversations]);

  const handleShowAdmin = useCallback(() => {
    setCurrentView("admin");
  }, []);

  if (isLoading) {
    return (
      <div className="loading-screen">
        <Loader2 size={32} className="spin" />
        <span>加载中...</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const renderConversationList = (collapsed: boolean) => (
    <ConversationList
      conversations={conversations.conversations}
      isLoading={conversations.isLoading}
      error={conversations.error}
      selectedId={conversations.selectedId}
      collapsed={collapsed}
      onSelect={handleSelectConversation}
      onUpdate={conversations.update}
      onDelete={conversations.remove}
    />
  );

  return (
    <MainLayout
      onNewConversation={handleNewConversation}
      onShowAdmin={handleShowAdmin}
      conversationList={renderConversationList}
      conversations={conversations.conversations}
      conversationsLoading={conversations.isLoading}
      conversationsError={conversations.error}
      selectedConversationId={conversations.selectedId}
      onSelectConversation={handleSelectConversation}
      onUpdateConversation={conversations.update}
      onDeleteConversation={conversations.remove}
    >
      {currentView === "chat" && (
        <ChatContainer key={chatKey} initialThreadId={currentThreadId} />
      )}
      {currentView === "admin" && <UserManagement />}
    </MainLayout>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
