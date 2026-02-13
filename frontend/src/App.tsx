import { useState, useCallback, useEffect } from "react";
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

  // Restore selected conversation on page load
  useEffect(() => {
    const restoreSelection = async () => {
      // If already have a threadId set or still loading, skip
      if (currentThreadId || conversations.isLoading) return;

      // Read saved ID from localStorage
      const savedId = localStorage.getItem("selected-conversation-id");
      if (!savedId) return;

      // Verify the conversation exists in current list
      const exists = conversations.conversations.find((c) => c.id === savedId);
      if (!exists) {
        localStorage.removeItem("selected-conversation-id");
        return;
      }

      // Restore selection and load conversation
      try {
        const conv = await getConversation(savedId);
        conversations.select(savedId);
        setCurrentThreadId(conv.thread_id);
        setChatKey((prev) => prev + 1);
      } catch (error) {
        console.error("Failed to restore conversation:", error);
        localStorage.removeItem("selected-conversation-id");
      }
    };

    restoreSelection();
  }, [conversations.isLoading, conversations.conversations]);

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
