"""Generator Agent - creates and modifies Commands and Skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from meta_agent.agents.base import BaseAgent, AgentContext, AgentResult
from meta_agent.agents.analyzer import AnalysisResult, ImprovementSuggestion
from meta_agent.models.plugin import Command, CommandFrontmatter, Skill, SkillFrontmatter
from meta_agent.services.file_service import FileService
from meta_agent.utils.git_utils import GitUtils


@dataclass
class FileChange:
    """Record of a file change."""

    file_path: str
    change_type: Literal["create", "update"]
    description: str
    git_commit_hash: str = ""


@dataclass
class GenerationResult:
    """Result of generation."""

    changes: list[FileChange] = field(default_factory=list)
    success: bool = True
    summary: str = ""


class GeneratorAgent(BaseAgent[GenerationResult]):
    """Agent responsible for generating and modifying Commands and Skills.

    Tasks:
    - Generate new Command files
    - Modify existing Command files
    - Generate new Skill files
    - Modify existing Skill files
    - Commit changes to git
    """

    def __init__(
        self,
        file_service: FileService,
        git_utils: GitUtils,
        api_key: str | None = None,
    ):
        """
        Initialize generator agent.

        Args:
            file_service: File service for plugin files
            git_utils: Git utilities
            api_key: Anthropic API key (optional)
        """
        super().__init__(
            name="Generator",
            description="Generates and modifies Commands and Skills",
            api_key=api_key,
        )
        self.file_service = file_service
        self.git_utils = git_utils

    async def run(self, context: AgentContext) -> AgentResult:
        """
        Generate modifications based on analysis.

        Args:
            context: Agent context with analysis_result

        Returns:
            Result with GenerationResult
        """
        start_time = datetime.now()
        self.log("Starting generation based on analysis")

        analysis: AnalysisResult | None = context.analysis_result
        if not analysis:
            return AgentResult.fail("No analysis result in context")

        if not analysis.suggestions:
            return AgentResult.ok(
                message="No suggestions to implement",
                data=GenerationResult(summary="No changes needed"),
            )

        try:
            changes: list[FileChange] = []

            # Process top suggestion (one at a time for better attribution)
            suggestion = analysis.suggestions[0]
            self.log(f"Processing suggestion: {suggestion.category.value}")

            # Generate modifications
            modification = await self._generate_modification(
                suggestion=suggestion,
                plugin_name=context.plugin_name,
            )

            if modification:
                change = await self._apply_modification(
                    modification=modification,
                    plugin_name=context.plugin_name,
                    commit_message=f"Fix {suggestion.category.value} issues",
                )
                if change:
                    changes.append(change)

            result = GenerationResult(
                changes=changes,
                success=len(changes) > 0,
                summary=f"Applied {len(changes)} changes",
            )

            context.generation_result = result

            duration = (datetime.now() - start_time).total_seconds()
            self.log(f"Generation complete: {len(changes)} changes")

            return AgentResult.ok(
                message=f"Generated {len(changes)} changes",
                data=result,
            )

        except Exception as e:
            self.log(f"Generation failed: {e}", "error")
            return AgentResult.fail(str(e))

    async def _generate_modification(
        self,
        suggestion: ImprovementSuggestion,
        plugin_name: str,
    ) -> dict[str, str] | None:
        """Generate a specific modification using LLM."""
        # Read current plugin state
        commands = self.file_service.list_commands(plugin_name)
        skills = self.file_service.list_skills(plugin_name)

        # Build context about current plugin
        plugin_context = f"""
Plugin: {plugin_name}
Commands: {', '.join(commands) if commands else 'None'}
Skills: {', '.join(skills) if skills else 'None'}
"""

        prompt = f"""Based on this analysis suggestion, generate a specific modification to fix the issue.

{plugin_context}

Suggestion:
Category: {suggestion.category.value}
Description: {suggestion.description}
Affected Cases: {', '.join(suggestion.affected_cases[:5])}

Determine the best modification:
1. If a Command needs to be modified, specify which one and the changes
2. If a Skill needs to be modified, specify which one and the changes
3. If a new Skill should be created, provide its definition

Respond in this format:
TYPE: [MODIFY_COMMAND | MODIFY_SKILL | CREATE_SKILL]
TARGET: [command_name or skill_name]
DESCRIPTION: [brief description of change]
CONTENT: [new content or diff]
"""

        try:
            response = await self.call_llm(
                system_prompt="You are a plugin developer. Generate specific file modifications.",
                user_message=prompt,
                max_tokens=2048,
            )

            return self._parse_modification_response(response)

        except Exception as e:
            self.log(f"Failed to generate modification: {e}", "warning")
            return None

    def _parse_modification_response(
        self,
        response: str,
    ) -> dict[str, str] | None:
        """Parse LLM response into modification dict."""
        result: dict[str, str] = {}

        for line in response.strip().split("\n"):
            if line.startswith("TYPE:"):
                result["type"] = line[5:].strip()
            elif line.startswith("TARGET:"):
                result["target"] = line[7:].strip()
            elif line.startswith("DESCRIPTION:"):
                result["description"] = line[12:].strip()
            elif line.startswith("CONTENT:"):
                # Rest of response is content
                content_start = response.find("CONTENT:") + 8
                result["content"] = response[content_start:].strip()
                break

        if "type" in result and "target" in result:
            return result
        return None

    async def _apply_modification(
        self,
        modification: dict[str, str],
        plugin_name: str,
        commit_message: str,
    ) -> FileChange | None:
        """Apply a modification to a file."""
        mod_type = modification.get("type", "")
        target = modification.get("target", "")
        content = modification.get("content", "")
        description = modification.get("description", "")

        if not target or not content:
            return None

        try:
            if mod_type == "MODIFY_COMMAND":
                # Read existing command
                try:
                    command = self.file_service.read_command(plugin_name, target)
                    # Backup before modification
                    self.file_service.backup_file(command.file_path)
                    change_type: Literal["create", "update"] = "update"
                except FileNotFoundError:
                    # Create new command
                    command = Command(
                        name=target,
                        plugin_name=plugin_name,
                        frontmatter=CommandFrontmatter(description=description),
                        content=content,
                    )
                    change_type = "create"

                # Update content
                command.content = content
                file_path = self.file_service.write_command(plugin_name, command)

            elif mod_type == "MODIFY_SKILL":
                # Read existing skill
                try:
                    skill = self.file_service.read_skill(plugin_name, target)
                    self.file_service.backup_file(skill.file_path)
                    change_type = "update"
                except FileNotFoundError:
                    return None  # Can't modify non-existent skill

                skill.content = content
                file_path = self.file_service.write_skill(plugin_name, skill)

            elif mod_type == "CREATE_SKILL":
                # Create new skill
                skill = Skill(
                    name=target,
                    plugin_name=plugin_name,
                    frontmatter=SkillFrontmatter(
                        name=target,
                        description=description,
                    ),
                    content=content,
                )
                file_path = self.file_service.write_skill(plugin_name, skill)
                change_type = "create"

            else:
                return None

            # Commit change
            commit_hash = ""
            try:
                commit_hash = self.git_utils.commit(
                    file_paths=[file_path],
                    message=commit_message,
                    prefix="meta-agent:",
                )
            except Exception as e:
                self.log(f"Git commit failed: {e}", "warning")

            return FileChange(
                file_path=file_path,
                change_type=change_type,
                description=description,
                git_commit_hash=commit_hash,
            )

        except Exception as e:
            self.log(f"Failed to apply modification: {e}", "error")
            return None

    async def rollback_change(self, change: FileChange) -> bool:
        """Rollback a specific change."""
        if not change.git_commit_hash:
            self.log("Cannot rollback: no commit hash", "warning")
            return False

        try:
            self.git_utils.revert_commit(change.git_commit_hash)
            self.log(f"Rolled back commit: {change.git_commit_hash[:7]}")
            return True
        except Exception as e:
            self.log(f"Rollback failed: {e}", "error")
            return False
