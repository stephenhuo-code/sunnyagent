# Diff Details

Date : 2026-02-17 14:25:06

Directory /Users/yanwen/Documents/github/sunnyagent

Total : 50 files,  6276 codes, 848 comments, 1226 blanks, all 8350 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [CLAUDE.md](/CLAUDE.md) | Markdown | 2 | 0 | 0 | 2 |
| [backend/agents/general.py](/backend/agents/general.py) | Python | 1 | 0 | 0 | 1 |
| [backend/aime/actors/generic.py](/backend/aime/actors/generic.py) | Python | 2 | 0 | 0 | 2 |
| [backend/conversations/database.py](/backend/conversations/database.py) | Python | 69 | 27 | 6 | 102 |
| [backend/conversations/models.py](/backend/conversations/models.py) | Python | 2 | 0 | 0 | 2 |
| [backend/conversations/router.py](/backend/conversations/router.py) | Python | 51 | 19 | 15 | 85 |
| [backend/main.py](/backend/main.py) | Python | 46 | 0 | 0 | 46 |
| [backend/models.py](/backend/models.py) | Python | 2 | 0 | 0 | 2 |
| [backend/projects/\_\_init\_\_.py](/backend/projects/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [backend/projects/database.py](/backend/projects/database.py) | Python | 197 | 68 | 43 | 308 |
| [backend/projects/models.py](/backend/projects/models.py) | Python | 45 | 19 | 36 | 100 |
| [backend/projects/router.py](/backend/projects/router.py) | Python | 237 | 51 | 60 | 348 |
| [backend/services/\_\_init\_\_.py](/backend/services/__init__.py) | Python | 8 | 3 | 3 | 14 |
| [backend/services/file\_context\_service.py](/backend/services/file_context_service.py) | Python | 248 | 74 | 48 | 370 |
| [backend/services/file\_extractor.py](/backend/services/file_extractor.py) | Python | 409 | 41 | 89 | 539 |
| [backend/tools/file\_tools.py](/backend/tools/file_tools.py) | Python | 101 | 38 | 28 | 167 |
| [docs/roadmap.md](/docs/roadmap.md) | Markdown | 23 | 0 | 7 | 30 |
| [frontend/src/App.tsx](/frontend/src/App.tsx) | TypeScript JSX | 77 | 8 | 8 | 93 |
| [frontend/src/api/client.ts](/frontend/src/api/client.ts) | TypeScript | 4 | 0 | 0 | 4 |
| [frontend/src/api/conversations.ts](/frontend/src/api/conversations.ts) | TypeScript | 9 | 0 | 2 | 11 |
| [frontend/src/api/projects.ts](/frontend/src/api/projects.ts) | TypeScript | 228 | 48 | 27 | 303 |
| [frontend/src/components/ChatContainer.tsx](/frontend/src/components/ChatContainer.tsx) | TypeScript JSX | 14 | 0 | 1 | 15 |
| [frontend/src/components/Conversations/ConversationItem.tsx](/frontend/src/components/Conversations/ConversationItem.tsx) | TypeScript JSX | 63 | 2 | 4 | 69 |
| [frontend/src/components/Conversations/ConversationList.tsx](/frontend/src/components/Conversations/ConversationList.tsx) | TypeScript JSX | 7 | 1 | 0 | 8 |
| [frontend/src/components/Conversations/Conversations.css](/frontend/src/components/Conversations/Conversations.css) | PostCSS | 50 | 1 | 8 | 59 |
| [frontend/src/components/InputBar.tsx](/frontend/src/components/InputBar.tsx) | TypeScript JSX | 16 | 0 | 0 | 16 |
| [frontend/src/components/Layout/MainLayout.tsx](/frontend/src/components/Layout/MainLayout.tsx) | TypeScript JSX | 3 | 0 | 0 | 3 |
| [frontend/src/components/Layout/Sidebar.tsx](/frontend/src/components/Layout/Sidebar.tsx) | TypeScript JSX | 24 | 2 | 1 | 27 |
| [frontend/src/components/Projects/NewProjectModal.tsx](/frontend/src/components/Projects/NewProjectModal.tsx) | TypeScript JSX | 85 | 3 | 12 | 100 |
| [frontend/src/components/Projects/ProjectItem.tsx](/frontend/src/components/Projects/ProjectItem.tsx) | TypeScript JSX | 209 | 4 | 25 | 238 |
| [frontend/src/components/Projects/ProjectList.tsx](/frontend/src/components/Projects/ProjectList.tsx) | TypeScript JSX | 160 | 6 | 13 | 179 |
| [frontend/src/components/Projects/ProjectSelectMenu.tsx](/frontend/src/components/Projects/ProjectSelectMenu.tsx) | TypeScript JSX | 78 | 3 | 9 | 90 |
| [frontend/src/components/Projects/ProjectWorkspace.tsx](/frontend/src/components/Projects/ProjectWorkspace.tsx) | TypeScript JSX | 81 | 5 | 9 | 95 |
| [frontend/src/components/Projects/Projects.css](/frontend/src/components/Projects/Projects.css) | PostCSS | 680 | 30 | 116 | 826 |
| [frontend/src/components/Projects/SourcesPanel.tsx](/frontend/src/components/Projects/SourcesPanel.tsx) | TypeScript JSX | 235 | 13 | 22 | 270 |
| [frontend/src/components/Projects/index.ts](/frontend/src/components/Projects/index.ts) | TypeScript | 6 | 3 | 2 | 11 |
| [frontend/src/hooks/useChat.ts](/frontend/src/hooks/useChat.ts) | TypeScript | 2 | 0 | 0 | 2 |
| [frontend/src/hooks/useConversations.ts](/frontend/src/hooks/useConversations.ts) | TypeScript | 4 | 2 | 1 | 7 |
| [frontend/src/hooks/useProjects.ts](/frontend/src/hooks/useProjects.ts) | TypeScript | 266 | 32 | 41 | 339 |
| [frontend/src/types/index.ts](/frontend/src/types/index.ts) | TypeScript | 26 | 7 | 4 | 37 |
| [infra/migrations/versions/004\_create\_projects\_table.py](/infra/migrations/versions/004_create_projects_table.py) | Python | 50 | 17 | 14 | 81 |
| [specs/006-project-management/checklists/requirements.md](/specs/006-project-management/checklists/requirements.md) | Markdown | 43 | 0 | 14 | 57 |
| [specs/006-project-management/contracts/projects\_api.py](/specs/006-project-management/contracts/projects_api.py) | Python | 46 | 297 | 39 | 382 |
| [specs/006-project-management/data-model.md](/specs/006-project-management/data-model.md) | Markdown | 195 | 0 | 55 | 250 |
| [specs/006-project-management/plan.md](/specs/006-project-management/plan.md) | Markdown | 108 | 0 | 28 | 136 |
| [specs/006-project-management/prototype.html](/specs/006-project-management/prototype.html) | HTML | 1,479 | 23 | 194 | 1,696 |
| [specs/006-project-management/quickstart.md](/specs/006-project-management/quickstart.md) | Markdown | 181 | 0 | 81 | 262 |
| [specs/006-project-management/research.md](/specs/006-project-management/research.md) | Markdown | 121 | 0 | 40 | 161 |
| [specs/006-project-management/spec.md](/specs/006-project-management/spec.md) | Markdown | 120 | 0 | 47 | 167 |
| [specs/006-project-management/tasks.md](/specs/006-project-management/tasks.md) | Markdown | 163 | 0 | 73 | 236 |

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details