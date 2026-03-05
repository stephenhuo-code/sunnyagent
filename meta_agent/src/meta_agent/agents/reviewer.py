"""Reviewer Agent - reviews generated content quality."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from meta_agent.agents.base import BaseAgent, AgentContext, AgentResult
from meta_agent.agents.generator import GenerationResult, FileChange
from meta_agent.services.file_service import FileService


@dataclass
class ReviewItem:
    """Review item for a single file."""

    file_path: str
    status: Literal["approved", "rejected", "needs_revision"]
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    score: float = 0.0  # Quality score [0, 1]


@dataclass
class ReviewResult:
    """Result of content review."""

    items: list[ReviewItem] = field(default_factory=list)
    all_approved: bool = True
    summary: str = ""


class ReviewerAgent(BaseAgent[ReviewResult]):
    """Agent responsible for reviewing generated content quality.

    Tasks:
    - Format validation (Command/Skill schema compliance)
    - Content quality check
    - Consistency verification with existing plugin structure
    """

    def __init__(
        self,
        file_service: FileService,
        api_key: str | None = None,
    ):
        """
        Initialize reviewer agent.

        Args:
            file_service: File service for reading files
            api_key: Anthropic API key (optional)
        """
        super().__init__(
            name="Reviewer",
            description="Reviews generated content for quality and compliance",
            api_key=api_key,
        )
        self.file_service = file_service

    async def run(self, context: AgentContext) -> AgentResult:
        """
        Review generated content.

        Args:
            context: Agent context with generation_result

        Returns:
            Result with ReviewResult
        """
        start_time = datetime.now()
        self.log("Reviewing generated content")

        generation: GenerationResult | None = context.generation_result
        if not generation:
            return AgentResult.fail("No generation result in context")

        if not generation.changes:
            return AgentResult.ok(
                message="No changes to review",
                data=ReviewResult(summary="No changes"),
            )

        try:
            items: list[ReviewItem] = []

            for change in generation.changes:
                review_item = await self._review_change(
                    change=change,
                    plugin_name=context.plugin_name,
                )
                items.append(review_item)

            all_approved = all(item.status == "approved" for item in items)

            result = ReviewResult(
                items=items,
                all_approved=all_approved,
                summary=self._generate_summary(items),
            )

            duration = (datetime.now() - start_time).total_seconds()
            self.log(
                f"Review complete: {len([i for i in items if i.status == 'approved'])}/{len(items)} approved"
            )

            return AgentResult.ok(
                message="Review complete",
                data=result,
            )

        except Exception as e:
            self.log(f"Review failed: {e}", "error")
            return AgentResult.fail(str(e))

    async def _review_change(
        self,
        change: FileChange,
        plugin_name: str,
    ) -> ReviewItem:
        """Review a single change."""
        issues: list[str] = []
        suggestions: list[str] = []

        try:
            # Read the file content
            content = self.file_service.read_file(change.file_path)

            # Basic format validation
            format_issues = self._validate_format(content, change.file_path)
            issues.extend(format_issues)

            # Content quality check using LLM
            quality_result = await self._check_quality(
                content=content,
                file_path=change.file_path,
                plugin_name=plugin_name,
            )
            issues.extend(quality_result.get("issues", []))
            suggestions.extend(quality_result.get("suggestions", []))
            quality_score = quality_result.get("score", 0.5)

            # Determine status
            if issues:
                if any("critical" in i.lower() for i in issues):
                    status: Literal["approved", "rejected", "needs_revision"] = "rejected"
                else:
                    status = "needs_revision"
            else:
                status = "approved"

            return ReviewItem(
                file_path=change.file_path,
                status=status,
                issues=issues,
                suggestions=suggestions,
                score=quality_score,
            )

        except FileNotFoundError:
            return ReviewItem(
                file_path=change.file_path,
                status="rejected",
                issues=["File not found"],
                score=0.0,
            )
        except Exception as e:
            return ReviewItem(
                file_path=change.file_path,
                status="rejected",
                issues=[f"Review error: {e}"],
                score=0.0,
            )

    def _validate_format(self, content: str, file_path: str) -> list[str]:
        """Validate file format."""
        issues = []

        # Check for frontmatter
        if not content.startswith("---"):
            issues.append("Missing YAML frontmatter")
        elif content.count("---") < 2:
            issues.append("Incomplete YAML frontmatter (missing closing ---)")

        # Check for required fields based on file type
        if "/commands/" in file_path:
            if "description:" not in content:
                issues.append("Command missing required 'description' field")
        elif "/skills/" in file_path:
            if "name:" not in content:
                issues.append("Skill missing required 'name' field")

        # Check content length
        if len(content.strip()) < 50:
            issues.append("Content too short (minimum 50 characters)")

        return issues

    async def _check_quality(
        self,
        content: str,
        file_path: str,
        plugin_name: str,
    ) -> dict[str, list[str] | float]:
        """Check content quality using LLM."""
        # Truncate content if too long
        max_content_length = 2000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n...[truncated]"

        prompt = f"""Review this plugin file for quality and suggest improvements.

File: {file_path}
Plugin: {plugin_name}

Content:
```
{content}
```

Evaluate:
1. Clarity and completeness of description
2. Proper structure and formatting
3. Useful instructions for the agent
4. Consistency with best practices

Respond in this format:
SCORE: [0.0-1.0]
ISSUES: [list any issues, or "None"]
SUGGESTIONS: [list improvements, or "None"]
"""

        try:
            response = await self.call_llm(
                system_prompt="You are a code reviewer specializing in AI agent configurations.",
                user_message=prompt,
                max_tokens=1024,
            )

            return self._parse_quality_response(response)

        except Exception as e:
            self.log(f"Quality check failed: {e}", "warning")
            return {"issues": [], "suggestions": [], "score": 0.5}

    def _parse_quality_response(
        self,
        response: str,
    ) -> dict[str, list[str] | float]:
        """Parse quality check response."""
        result: dict[str, list[str] | float] = {
            "issues": [],
            "suggestions": [],
            "score": 0.5,
        }

        for line in response.strip().split("\n"):
            if line.startswith("SCORE:"):
                try:
                    result["score"] = float(line[6:].strip())
                except ValueError:
                    pass
            elif line.startswith("ISSUES:"):
                issues_text = line[7:].strip()
                if issues_text.lower() != "none":
                    issues = [i.strip() for i in issues_text.split(",") if i.strip()]
                    result["issues"] = issues
            elif line.startswith("SUGGESTIONS:"):
                suggestions_text = line[12:].strip()
                if suggestions_text.lower() != "none":
                    suggestions = [s.strip() for s in suggestions_text.split(",") if s.strip()]
                    result["suggestions"] = suggestions

        return result

    def _generate_summary(self, items: list[ReviewItem]) -> str:
        """Generate review summary."""
        approved = sum(1 for i in items if i.status == "approved")
        rejected = sum(1 for i in items if i.status == "rejected")
        needs_revision = sum(1 for i in items if i.status == "needs_revision")

        lines = [
            f"## Review Summary",
            f"",
            f"- Approved: {approved}",
            f"- Needs Revision: {needs_revision}",
            f"- Rejected: {rejected}",
        ]

        if any(i.issues for i in items):
            lines.extend([
                f"",
                f"### Issues Found",
            ])
            for item in items:
                if item.issues:
                    lines.append(f"- {item.file_path}:")
                    for issue in item.issues[:3]:
                        lines.append(f"  - {issue}")

        return "\n".join(lines)
