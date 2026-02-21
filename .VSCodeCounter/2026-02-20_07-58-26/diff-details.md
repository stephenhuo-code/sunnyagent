# Diff Details

Date : 2026-02-20 07:58:26

Directory /Users/yanwen/Documents/github/sunnyagent

Total : 59 files,  2714 codes, 385 comments, 837 blanks, all 3936 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [CLAUDE.md](/CLAUDE.md) | Markdown | 17 | 0 | 2 | 19 |
| [backend/agents/general.py](/backend/agents/general.py) | Python | -1 | 1 | 2 | 2 |
| [backend/agents/research.py](/backend/agents/research.py) | Python | 1 | 0 | 0 | 1 |
| [backend/agents/sql.py](/backend/agents/sql.py) | Python | 2 | 0 | 0 | 2 |
| [backend/aime/actor\_factory.py](/backend/aime/actor_factory.py) | Python | 39 | 1 | 3 | 43 |
| [backend/aime/actors/generic.py](/backend/aime/actors/generic.py) | Python | 2 | 0 | 0 | 2 |
| [backend/aime/context.py](/backend/aime/context.py) | Python | 79 | 84 | 22 | 185 |
| [backend/aime/intent/\_\_init\_\_.py](/backend/aime/intent/__init__.py) | Python | 0 | -1 | 0 | -1 |
| [backend/aime/intent/analyzer.py](/backend/aime/intent/analyzer.py) | Python | 65 | 8 | 10 | 83 |
| [backend/aime/intent/classifiers/\_\_init\_\_.py](/backend/aime/intent/classifiers/__init__.py) | Python | -2 | 4 | 0 | 2 |
| [backend/aime/intent/classifiers/keyword\_based.py](/backend/aime/intent/classifiers/keyword_based.py) | Python | -105 | -32 | -21 | -158 |
| [backend/aime/intent/classifiers/llm\_based.py](/backend/aime/intent/classifiers/llm_based.py) | Python | 12 | -1 | 0 | 11 |
| [backend/aime/planner.py](/backend/aime/planner.py) | Python | 157 | 20 | 20 | 197 |
| [backend/api/\_\_init\_\_.py](/backend/api/__init__.py) | Python | 25 | 15 | 8 | 48 |
| [backend/auth/database.py](/backend/auth/database.py) | Python | 83 | 29 | 32 | 144 |
| [backend/core/\_\_init\_\_.py](/backend/core/__init__.py) | Python | 5 | 1 | 3 | 9 |
| [backend/core/chat.py](/backend/core/chat.py) | Python | 152 | 49 | 34 | 235 |
| [backend/core/files.py](/backend/core/files.py) | Python | 145 | 35 | 30 | 210 |
| [backend/core/skills.py](/backend/core/skills.py) | Python | 27 | 4 | 10 | 41 |
| [backend/core/system\_router.py](/backend/core/system_router.py) | Python | 13 | 10 | 8 | 31 |
| [backend/main.py](/backend/main.py) | Python | -229 | -188 | -23 | -440 |
| [backend/prompts.py](/backend/prompts.py) | Python | 2 | 0 | 0 | 2 |
| [backend/research\_prompts.py](/backend/research_prompts.py) | Python | 2 | 0 | 0 | 2 |
| [backend/services/langfuse\_admin\_client.py](/backend/services/langfuse_admin_client.py) | Python | 175 | 67 | 35 | 277 |
| [backend/services/langfuse\_service.py](/backend/services/langfuse_service.py) | Python | 120 | 59 | 34 | 213 |
| [backend/supervisor.py](/backend/supervisor.py) | Python | 1 | 0 | 0 | 1 |
| [backend/tools/file\_tools.py](/backend/tools/file_tools.py) | Python | 75 | 36 | 18 | 129 |
| [docker-compose.yml](/docker-compose.yml) | YAML | 141 | 6 | 5 | 152 |
| [docs/AIME-agent-Core.md](/docs/AIME-agent-Core.md) | Markdown | 632 | 0 | 49 | 681 |
| [docs/Architecture-AIMEAgent-Core.md](/docs/Architecture-AIMEAgent-Core.md) | Markdown | -632 | 0 | -49 | -681 |
| [docs/api.md](/docs/api.md) | Markdown | 612 | 0 | 235 | 847 |
| [docs/architecture.md](/docs/architecture.md) | Markdown | 80 | 0 | 10 | 90 |
| [docs/current-architecture.md](/docs/current-architecture.md) | Markdown | -461 | 0 | -29 | -490 |
| [docs/current-feature-description.md](/docs/current-feature-description.md) | Markdown | -621 | 0 | -179 | -800 |
| [docs/langfuse-playground.md](/docs/langfuse-playground.md) | Markdown | 155 | 0 | 58 | 213 |
| [docs/prototype.html](/docs/prototype.html) | HTML | -981 | -13 | -127 | -1,121 |
| [docs/roadmap.md](/docs/roadmap.md) | Markdown | 12 | 0 | 1 | 13 |
| [frontend/src/components/Admin/Admin.css](/frontend/src/components/Admin/Admin.css) | PostCSS | 120 | 6 | 25 | 151 |
| [frontend/src/components/Admin/AdminPanel.tsx](/frontend/src/components/Admin/AdminPanel.tsx) | TypeScript JSX | 33 | 3 | 6 | 42 |
| [frontend/src/components/Admin/SystemSettings.tsx](/frontend/src/components/Admin/SystemSettings.tsx) | TypeScript JSX | 137 | 3 | 16 | 156 |
| [frontend/src/components/Admin/index.ts](/frontend/src/components/Admin/index.ts) | TypeScript | 2 | 0 | 0 | 2 |
| [infra/init-langfuse-db.sql](/infra/init-langfuse-db.sql) | MS SQL | 2 | 2 | 2 | 6 |
| [infra/migrations/versions/005\_create\_langfuse\_user\_mapping.py](/infra/migrations/versions/005_create_langfuse_user_mapping.py) | Python | 29 | 11 | 9 | 49 |
| [scripts/evaluation/README.md](/scripts/evaluation/README.md) | Markdown | 140 | 0 | 49 | 189 |
| [scripts/evaluation/evaluators.py](/scripts/evaluation/evaluators.py) | Python | 185 | 39 | 32 | 256 |
| [scripts/evaluation/run\_experiment.py](/scripts/evaluation/run_experiment.py) | Python | 181 | 55 | 46 | 282 |
| [scripts/evaluation/sample\_dataset.json](/scripts/evaluation/sample_dataset.json) | JSON | 148 | 0 | 1 | 149 |
| [scripts/evaluation/tool\_schemas/sunnyagent\_tools.json](/scripts/evaluation/tool_schemas/sunnyagent_tools.json) | JSON | 123 | 0 | 1 | 124 |
| [scripts/evaluation/validate\_langfuse.py](/scripts/evaluation/validate_langfuse.py) | Python | 266 | 35 | 56 | 357 |
| [scripts/start.sh](/scripts/start.sh) | Shell Script | 176 | 37 | 37 | 250 |
| [specs/007-langfuse-integration/checklists/requirements.md](/specs/007-langfuse-integration/checklists/requirements.md) | Markdown | 32 | 0 | 10 | 42 |
| [specs/007-langfuse-integration/contracts/langfuse-admin-api.yaml](/specs/007-langfuse-integration/contracts/langfuse-admin-api.yaml) | YAML | 213 | 0 | 14 | 227 |
| [specs/007-langfuse-integration/data-model.md](/specs/007-langfuse-integration/data-model.md) | Markdown | 154 | 0 | 45 | 199 |
| [specs/007-langfuse-integration/plan.md](/specs/007-langfuse-integration/plan.md) | Markdown | 82 | 0 | 25 | 107 |
| [specs/007-langfuse-integration/quickstart.md](/specs/007-langfuse-integration/quickstart.md) | Markdown | 182 | 0 | 68 | 250 |
| [specs/007-langfuse-integration/research.md](/specs/007-langfuse-integration/research.md) | Markdown | 243 | 0 | 55 | 298 |
| [specs/007-langfuse-integration/spec.md](/specs/007-langfuse-integration/spec.md) | Markdown | 126 | 0 | 61 | 187 |
| [specs/007-langfuse-integration/tasks.md](/specs/007-langfuse-integration/tasks.md) | Markdown | 152 | 0 | 67 | 219 |
| [uv.lock](/uv.lock) | toml | 189 | 0 | 11 | 200 |

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details