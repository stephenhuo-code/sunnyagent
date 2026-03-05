"""Environment Setup Agent - prepares test environment."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from meta_agent.agents.base import BaseAgent, AgentContext, AgentResult
from meta_agent.models.dataset import TestDataset, TestFile
from meta_agent.services.sunnyagent_client import SunnyAgentClient


class EnvironmentSetupAgent(BaseAgent[dict[str, str]]):
    """Agent responsible for preparing test environment.

    Tasks:
    - Create test project in SunnyAgent
    - Upload test files to project
    - Validate context_files exist
    """

    def __init__(
        self,
        sunnyagent_client: SunnyAgentClient,
        base_dir: str,
        api_key: str | None = None,
    ):
        """
        Initialize environment setup agent.

        Args:
            sunnyagent_client: SunnyAgent API client
            base_dir: Base directory for meta_agent
            api_key: Anthropic API key (optional)
        """
        super().__init__(
            name="EnvironmentSetup",
            description="Prepares test environment: creates projects, uploads files",
            api_key=api_key,
        )
        self.sunnyagent = sunnyagent_client
        self.base_dir = Path(base_dir)
        self.files_dir = self.base_dir / "test-resources" / "files"

    async def run(self, context: AgentContext) -> AgentResult:
        """
        Prepare test environment.

        Args:
            context: Agent context with project_name

        Returns:
            Result with project_id and file_id_map
        """
        start_time = datetime.now()
        self.log(f"Setting up environment for project: {context.project_name}")

        try:
            # Login to SunnyAgent
            await self.sunnyagent.login()
            self.log("Logged in to SunnyAgent")

            # Get or create project
            project = await self.sunnyagent.get_project(context.project_name)
            if project:
                self.log(f"Using existing project: {project.id}")
            else:
                project = await self.sunnyagent.create_project(
                    name=context.project_name,
                    description="Meta-Agent test project",
                )
                self.log(f"Created project: {project.id}")

            context.project_id = project.id

            # Get files to upload from context metadata
            dataset: TestDataset | None = context.metadata.get("dataset")
            if dataset:
                files_to_upload = self._get_files_to_upload(dataset)
                file_id_map = await self._upload_files(project.id, files_to_upload)
                context.file_id_map = file_id_map
                self.log(f"Uploaded {len(file_id_map)} files")
            else:
                context.file_id_map = {}

            duration = (datetime.now() - start_time).total_seconds()
            return AgentResult.ok(
                message=f"Environment ready (project: {context.project_id})",
                data={
                    "project_id": context.project_id,
                    "file_id_map": context.file_id_map,
                },
            )

        except Exception as e:
            self.log(f"Failed to setup environment: {e}", "error")
            return AgentResult.fail(str(e))

    def _get_files_to_upload(self, dataset: TestDataset) -> list[TestFile]:
        """Get all unique files to upload from dataset."""
        files: dict[str, TestFile] = {}

        for file_path in dataset.get_all_context_files():
            if file_path not in files:
                full_path = self.files_dir / file_path
                if full_path.exists():
                    files[file_path] = TestFile(
                        relative_path=file_path,
                        file_size=full_path.stat().st_size,
                        file_type=full_path.suffix.lstrip("."),
                    )

        return list(files.values())

    async def _upload_files(
        self,
        project_id: str,
        files: list[TestFile],
    ) -> dict[str, str]:
        """Upload files to project."""
        file_id_map: dict[str, str] = {}

        for test_file in files:
            try:
                full_path = self.files_dir / test_file.relative_path
                file_info = await self.sunnyagent.upload_file(
                    project_id=project_id,
                    file_path=str(full_path),
                )
                file_id_map[test_file.relative_path] = file_info.id
                test_file.sunnyagent_file_id = file_info.id
                self.log(f"Uploaded: {test_file.relative_path}", "debug")
            except Exception as e:
                self.log(f"Failed to upload {test_file.relative_path}: {e}", "warning")

        return file_id_map

    def validate_context_files(self, dataset: TestDataset) -> list[str]:
        """
        Validate all context files exist.

        Returns:
            List of missing file paths
        """
        missing = []
        for file_path in dataset.get_all_context_files():
            full_path = self.files_dir / file_path
            if not full_path.exists():
                missing.append(file_path)
        return missing

    async def cleanup(
        self,
        context: AgentContext,
        delete_project: bool = False,
    ) -> None:
        """Clean up test environment."""
        if delete_project and context.project_id:
            try:
                await self.sunnyagent.delete_project(context.project_id)
                self.log(f"Deleted project: {context.project_id}")
            except Exception as e:
                self.log(f"Failed to delete project: {e}", "warning")

        await self.sunnyagent.logout()
