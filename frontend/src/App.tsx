import { useState, useCallback, useEffect } from "react";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { useConversations } from "./hooks/useConversations";
import { useProjects } from "./hooks/useProjects";
import { useSkills } from "./hooks/useSkills";
import { LoginPage } from "./components/Auth/LoginPage";
import { MainLayout } from "./components/Layout/MainLayout";
import { ConversationList } from "./components/Conversations";
import { AdminPanel } from "./components/Admin";
import ChatContainer from "./components/ChatContainer";
import { ProjectList, ProjectHome, ProjectWorkspace } from "./components/Projects";
import { PluginsPage } from "./pages/PluginsPage";
import { Loader2, X } from "lucide-react";
import { getConversation } from "./api/conversations";

type View = "chat" | "project" | "plugins";

function AppContent() {
  const { isAuthenticated, isLoading } = useAuth();
  const [currentView, setCurrentView] = useState<View>("chat");
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  const [chatKey, setChatKey] = useState(0);
  const [showProjectHome, setShowProjectHome] = useState(true);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [showAdminModal, setShowAdminModal] = useState(false);

  const conversations = useConversations();
  const projects = useProjects();
  const { skills } = useSkills();
  const [createProjectTrigger, setCreateProjectTrigger] = useState(0);

  // Close admin modal on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && showAdminModal) {
        setShowAdminModal(false);
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [showAdminModal]);

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
    setShowAdminModal(true);
  }, []);

  const handleSelectProject = useCallback(async (id: string) => {
    projects.select(id);
    setCurrentView("project");
    setCurrentThreadId(null);
    setShowProjectHome(true);  // Show project home page
    // Load project files and conversations
    projects.loadFiles(id);
    projects.loadConversations(id);
  }, [projects]);

  const handleProjectConversationSelect = useCallback(async (conversationId: string, projectId: string) => {
    try {
      const conv = await getConversation(conversationId);
      conversations.select(conversationId);
      projects.select(projectId);
      setCurrentThreadId(conv.thread_id);
      setChatKey((prev) => prev + 1);
      setCurrentView("project");
      setShowProjectHome(false);  // Exit project home, show conversation
    } catch (err) {
      console.error("Failed to load conversation:", err);
    }
  }, [conversations, projects]);

  // Handle removing conversation from project (and refresh conversations list)
  const handleRemoveConversationFromProject = useCallback(async (conversationId: string, projectId: string) => {
    await projects.removeConversation(conversationId, projectId);
    // Refresh conversations list to add the conversation back to history
    await conversations.refresh();
  }, [projects, conversations]);

  // Handle adding conversation to project (and refresh conversations list)
  const handleAddConversationToProject = useCallback(async (conversationId: string, projectId: string) => {
    await projects.addConversation(conversationId, projectId);
    // Refresh conversations list to move the conversation out of history
    await conversations.refresh();
  }, [projects, conversations]);

  // Handle conversation created in project workspace (refresh project conversations)
  const handleProjectConversationCreated = useCallback(async () => {
    // Clear the pending message after conversation is created
    setPendingMessage(null);
    if (projects.selectedProjectId) {
      // Refresh project conversations to show the newly created conversation
      await projects.loadConversations(projects.selectedProjectId);
    }
  }, [projects]);

  // Handle creating a new conversation from project home page
  const handleCreateConversationFromHome = useCallback(async (message: string) => {
    if (!projects.selectedProjectId) return;

    try {
      // 1. Create new conversation in the project
      const conv = await conversations.createInProject(projects.selectedProjectId);

      // 2. Set up chat context
      setCurrentThreadId(conv.thread_id);
      setChatKey((prev) => prev + 1);

      // 3. Store the pending message to be sent after ChatContainer mounts
      setPendingMessage(message);

      // 4. Exit project home, show conversation view
      setShowProjectHome(false);

      // 5. Refresh project conversations list
      await projects.loadConversations(projects.selectedProjectId);
    } catch (err) {
      console.error("Failed to create conversation from home:", err);
    }
  }, [projects, conversations]);

  // Handle adding a new conversation in project from sidebar
  const handleAddConversationInProject = useCallback(async (projectId: string) => {
    try {
      // 1. Create new conversation in the project
      const conv = await conversations.createInProject(projectId);

      // 2. Select the project and conversation
      projects.select(projectId);
      conversations.select(conv.id);

      // 3. Set up chat context
      setCurrentThreadId(conv.thread_id);
      setChatKey((prev) => prev + 1);

      // 4. Switch to project view and exit home
      setCurrentView("project");
      setShowProjectHome(false);

      // 5. Refresh project conversations list
      await projects.loadConversations(projectId);
    } catch (err) {
      console.error("Failed to create conversation in project:", err);
    }
  }, [projects, conversations]);

  // Handle deleting a conversation from project sidebar
  const handleDeleteConversationInProject = useCallback(async (conversationId: string) => {
    try {
      await conversations.remove(conversationId);
      // Refresh project conversations list
      if (projects.selectedProjectId) {
        await projects.loadConversations(projects.selectedProjectId);
      }
      // If the deleted conversation was selected, clear selection
      if (conversations.selectedId === conversationId) {
        setCurrentThreadId(null);
        setShowProjectHome(true);
      }
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    }
  }, [conversations, projects]);

  // Handle renaming a conversation from project sidebar
  const handleRenameConversationInProject = useCallback(async (conversationId: string, title: string) => {
    try {
      await conversations.update(conversationId, title);
      // Refresh project conversations list
      if (projects.selectedProjectId) {
        await projects.loadConversations(projects.selectedProjectId);
      }
    } catch (err) {
      console.error("Failed to rename conversation:", err);
    }
  }, [conversations, projects]);


  // Handle file upload trigger from project home
  const handleUploadFileFromHome = useCallback(() => {
    // Create a file input and trigger click
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".pdf,.docx,.txt,.md,.csv,.json,.py,.js,.ts,.tsx,.jsx,.java,.go,.c,.cpp,.h,.hpp,.rs,.rb,.php,.swift,.kt";
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file && projects.selectedProjectId) {
        await projects.uploadFile(projects.selectedProjectId, file);
      }
    };
    input.click();
  }, [projects]);

  // Handle opening the create project modal (must be before conditional returns)
  const handleOpenCreateProjectModal = useCallback(() => {
    setCreateProjectTrigger(prev => prev + 1);
  }, []);

  // Handle showing plugins page
  const handleShowPlugins = useCallback(() => {
    setCurrentView("plugins");
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
      conversations={conversations.historyConversations}
      isLoading={conversations.isLoading}
      error={conversations.error}
      selectedId={conversations.selectedId}
      collapsed={collapsed}
      onSelect={handleSelectConversation}
      onUpdate={conversations.update}
      onDelete={conversations.remove}
      projects={projects.projects}
      onAddToProject={handleAddConversationToProject}
    />
  );

  const renderProjectsList = (collapsed: boolean) => (
    <ProjectList
      projects={projects.projects}
      openCreateModalTrigger={createProjectTrigger}
      isLoading={projects.isLoading}
      error={projects.error}
      selectedProjectId={projects.selectedProjectId}
      collapsed={collapsed}
      selectedConversationId={conversations.selectedId}
      onSelectProject={handleSelectProject}
      onCreateProject={async (name) => { await projects.create(name); }}
      onRenameProject={projects.update}
      onDeleteProject={projects.remove}
      getProjectConversations={projects.getConversations}
      isConversationsLoading={projects.isConversationsLoading}
      onLoadConversations={projects.loadConversations}
      onSelectConversation={handleProjectConversationSelect}
      onRemoveConversation={handleRemoveConversationFromProject}
      onDeleteConversation={handleDeleteConversationInProject}
      onRenameConversation={handleRenameConversationInProject}
      onAddConversation={handleAddConversationInProject}
    />
  );

  // Find current project for workspace
  const currentProject = projects.projects.find(p => p.id === projects.selectedProjectId);

  return (
    <>
      <MainLayout
        onNewConversation={handleNewConversation}
        onShowAdmin={handleShowAdmin}
        onShowPlugins={handleShowPlugins}
        conversationList={renderConversationList}
        projectsSection={renderProjectsList}
        conversations={conversations.historyConversations}
        conversationsLoading={conversations.isLoading}
        conversationsError={conversations.error}
        selectedConversationId={conversations.selectedId}
        onSelectConversation={handleSelectConversation}
        onUpdateConversation={conversations.update}
        onDeleteConversation={conversations.remove}
        onCreateProject={handleOpenCreateProjectModal}
        projects={projects.projects}
        projectsLoading={projects.isLoading}
        projectsError={projects.error}
        selectedProjectId={projects.selectedProjectId}
        onSelectProject={handleSelectProject}
      >
        {currentView === "chat" && (
          <ChatContainer key={chatKey} initialThreadId={currentThreadId} />
        )}
        {currentView === "plugins" && <PluginsPage />}
        {currentView === "project" && currentProject && (
          showProjectHome ? (
            <ProjectHome
              project={currentProject}
              files={projects.files}
              conversations={projects.getConversations(currentProject.id)}
              conversationsLoading={projects.isConversationsLoading(currentProject.id)}
              skills={skills}
              onCreateConversation={handleCreateConversationFromHome}
              onSelectConversation={(convId) => handleProjectConversationSelect(convId, currentProject.id)}
              onUploadFile={handleUploadFileFromHome}
            />
          ) : (
            <ProjectWorkspace
              projectId={currentProject.id}
              projectName={currentProject.name}
              threadId={currentThreadId}
              files={projects.files}
              filesLoading={projects.filesLoading}
              selectedFileIds={projects.selectedFileIds}
              uploadingFiles={projects.uploadingFiles}
              onLoadFiles={projects.loadFiles}
              onUploadFile={projects.uploadFile}
              onDeleteFile={projects.removeFile}
              onRenameFile={projects.renameFile}
              onToggleFileSelection={projects.toggleFileSelection}
              onSelectAllFiles={projects.selectAllFiles}
              onClearFileSelection={projects.clearFileSelection}
              onConversationCreated={handleProjectConversationCreated}
              initialMessage={pendingMessage}
            />
          )
        )}
      </MainLayout>

      {/* Admin Modal */}
      {showAdminModal && (
        <div className="admin-modal-overlay" onClick={() => setShowAdminModal(false)}>
          <div className="admin-modal-container" onClick={(e) => e.stopPropagation()}>
            <button
              className="admin-modal-close"
              onClick={() => setShowAdminModal(false)}
              aria-label="Close admin panel"
            >
              <X size={20} />
            </button>
            <AdminPanel />
          </div>
        </div>
      )}
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
