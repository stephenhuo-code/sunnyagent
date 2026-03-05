"""Dataset service for test dataset management."""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from meta_agent.models.dataset import TestCase, TestDataset, TestFile, Message, ProjectConfig
from meta_agent.services.langfuse_client import LangfuseClient

logger = logging.getLogger(__name__)


class DatasetValidationError(Exception):
    """Dataset validation error."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Validation failed with {len(errors)} errors")


class DatasetService:
    """Dataset management service.

    Handles:
    - Dataset validation (JSONL/CSV)
    - Context files checking
    - Langfuse sync
    - Incremental updates
    """

    def __init__(
        self,
        base_dir: str,
        langfuse_client: LangfuseClient | None = None,
    ):
        """
        Initialize dataset service.

        Args:
            base_dir: Base directory for meta_agent (contains test-resources/)
            langfuse_client: Langfuse client for sync operations
        """
        self.base_dir = Path(base_dir)
        self.datasets_dir = self.base_dir / "test-resources" / "datasets"
        self.files_dir = self.base_dir / "test-resources" / "files"
        self.langfuse = langfuse_client

    def load_dataset(self, dataset_path: str) -> TestDataset:
        """
        Load and validate dataset from file.

        Args:
            dataset_path: Path to dataset file (JSONL or CSV)

        Returns:
            Validated TestDataset

        Raises:
            DatasetValidationError: If validation fails
            FileNotFoundError: If file not found
        """
        path = Path(dataset_path)
        if not path.is_absolute():
            path = self.base_dir / dataset_path

        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

        # Determine format and parse
        if path.suffix.lower() == ".jsonl":
            cases = self._parse_jsonl(path)
        elif path.suffix.lower() == ".csv":
            cases = self._parse_csv(path)
        else:
            raise DatasetValidationError(
                [f"Unsupported file format: {path.suffix}. Use .jsonl or .csv"]
            )

        # Validate cases
        errors = self._validate_cases(cases)
        if errors:
            raise DatasetValidationError(errors)

        # Extract plugin name from first case or filename
        plugin_name = self._extract_plugin_name(cases, path)

        # Create dataset
        dataset = TestDataset(
            name=path.stem,
            plugin_name=plugin_name,
            cases=cases,
            source_file=str(path),
        )

        # Validate context files exist
        file_errors = self._validate_context_files(dataset)
        if file_errors:
            raise DatasetValidationError(file_errors)

        return dataset

    def _parse_jsonl(self, path: Path) -> list[TestCase]:
        """Parse JSONL file."""
        cases = []
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    data = json.loads(line)
                    # Skip comment lines (lines with _comment field)
                    if "_comment" in data:
                        continue
                    case = self._dict_to_test_case(data)
                    cases.append(case)
                except json.JSONDecodeError as e:
                    raise DatasetValidationError(
                        [f"Line {line_num}: Invalid JSON - {e}"]
                    )
                except Exception as e:
                    raise DatasetValidationError(
                        [f"Line {line_num}: {e}"]
                    )
        return cases

    def _parse_csv(self, path: Path) -> list[TestCase]:
        """Parse CSV file."""
        cases = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, 2):  # Start at 2 (header is 1)
                try:
                    # Parse JSON arrays in CSV fields
                    data = {}
                    for key, value in row.items():
                        if key in (
                            "expected_output_contains",
                            "tags",
                            "context_files",
                        ):
                            if value and value.strip():
                                try:
                                    data[key] = json.loads(value)
                                except json.JSONDecodeError:
                                    data[key] = [v.strip() for v in value.split(",")]
                            else:
                                data[key] = []
                        elif key == "conversation_history":
                            if value and value.strip():
                                data[key] = json.loads(value)
                            else:
                                data[key] = []
                        elif key == "project_config":
                            if value and value.strip():
                                data[key] = json.loads(value)
                            else:
                                data[key] = None
                        else:
                            data[key] = value

                    case = self._dict_to_test_case(data)
                    cases.append(case)
                except Exception as e:
                    raise DatasetValidationError(
                        [f"Row {row_num}: {e}"]
                    )
        return cases

    def _dict_to_test_case(self, data: dict[str, Any]) -> TestCase:
        """Convert dictionary to TestCase."""
        # Handle conversation_history
        history = []
        for msg in data.get("conversation_history", []):
            if isinstance(msg, dict):
                history.append(Message(**msg))
            elif isinstance(msg, Message):
                history.append(msg)

        # Handle project_config
        project_config = None
        if data.get("project_config"):
            if isinstance(data["project_config"], dict):
                project_config = ProjectConfig(**data["project_config"])
            elif isinstance(data["project_config"], ProjectConfig):
                project_config = data["project_config"]

        return TestCase(
            case_id=data["case_id"],
            input=data["input"],
            context_files=data.get("context_files", []),
            conversation_history=history,
            command=data.get("command"),
            expected_skill=data.get("expected_skill"),
            expected_output_contains=data.get("expected_output_contains", []),
            expected_behavior=data["expected_behavior"],
            tags=data.get("tags", []),
            project_config=project_config,
        )

    def _validate_cases(self, cases: list[TestCase]) -> list[str]:
        """Validate test cases."""
        errors = []

        if not cases:
            errors.append("Dataset must contain at least one test case")
            return errors

        # Check unique case_ids
        case_ids = [c.case_id for c in cases]
        duplicates = [cid for cid in case_ids if case_ids.count(cid) > 1]
        if duplicates:
            errors.append(f"Duplicate case_ids: {set(duplicates)}")

        return errors

    def _validate_context_files(self, dataset: TestDataset) -> list[str]:
        """Validate all context files exist."""
        errors = []
        all_files = dataset.get_all_context_files()

        for file_path in all_files:
            full_path = self.files_dir / file_path
            if not full_path.exists():
                errors.append(f"Context file not found: {file_path}")

        return errors

    def _extract_plugin_name(
        self,
        cases: list[TestCase],
        path: Path,
    ) -> str:
        """Extract plugin name from cases or filename."""
        # Try to get from first case's command
        for case in cases:
            if case.command:
                # Assume plugin name is part of command or filename
                break

        # Default to filename pattern: {plugin}-{version}.jsonl
        name = path.stem
        if "-v" in name:
            return name.rsplit("-v", 1)[0]
        return name

    def get_test_files(self, dataset: TestDataset) -> list[TestFile]:
        """Get all test files for a dataset."""
        files = []
        for file_path in dataset.get_all_context_files():
            full_path = self.files_dir / file_path
            if full_path.exists():
                files.append(
                    TestFile(
                        relative_path=file_path,
                        file_size=full_path.stat().st_size,
                        file_type=full_path.suffix.lstrip("."),
                    )
                )
        return files

    # Langfuse Sync

    async def sync_to_langfuse(
        self,
        dataset: TestDataset,
        force_new: bool = False,
    ) -> str:
        """
        Sync dataset to Langfuse.

        Args:
            dataset: Dataset to sync
            force_new: Force create new dataset (don't update existing)

        Returns:
            Langfuse dataset ID
        """
        if not self.langfuse:
            raise RuntimeError("Langfuse client not configured")

        langfuse_name = f"meta-agent-{dataset.name}-{dataset.version}"

        # Check if exists
        if not force_new:
            existing = await self.langfuse.get_dataset(langfuse_name)
            if existing:
                # Update existing
                await self._update_langfuse_dataset(langfuse_name, dataset)
                dataset.langfuse_dataset_id = existing["id"]
                dataset.last_synced_at = datetime.now()
                return existing["id"]

        # Create new
        dataset_id = await self.langfuse.create_dataset(
            name=langfuse_name,
            description=f"Test dataset for {dataset.plugin_name}",
            metadata={
                "plugin": dataset.plugin_name,
                "version": dataset.version,
                "source_file": dataset.source_file,
            },
        )

        # Add items
        for case in dataset.cases:
            await self.langfuse.create_dataset_item(
                dataset_name=langfuse_name,
                input_data={
                    "input": case.input,
                    "context_files": case.context_files,
                    "conversation_history": [
                        {"role": m.role, "content": m.content}
                        for m in case.conversation_history
                    ],
                },
                expected_output={
                    "skill": case.expected_skill,
                    "contains": case.expected_output_contains,
                    "behavior": case.expected_behavior,
                },
                metadata={
                    "case_id": case.case_id,
                    "command": case.command,
                    "tags": case.tags,
                },
            )

        dataset.langfuse_dataset_id = dataset_id
        dataset.last_synced_at = datetime.now()
        logger.info(f"Synced dataset to Langfuse: {langfuse_name}")

        return dataset_id

    async def _update_langfuse_dataset(
        self,
        langfuse_name: str,
        dataset: TestDataset,
    ) -> None:
        """Update existing Langfuse dataset."""
        if not self.langfuse:
            return

        # For simplicity, add all items (Langfuse handles deduplication)
        for case in dataset.cases:
            await self.langfuse.create_dataset_item(
                dataset_name=langfuse_name,
                input_data={
                    "input": case.input,
                    "context_files": case.context_files,
                },
                expected_output={
                    "skill": case.expected_skill,
                    "contains": case.expected_output_contains,
                },
                metadata={
                    "case_id": case.case_id,
                    "command": case.command,
                    "tags": case.tags,
                },
            )

    def save_dataset(self, dataset: TestDataset, output_path: str) -> None:
        """Save dataset to file."""
        path = Path(output_path)

        if path.suffix.lower() == ".jsonl":
            self._save_jsonl(dataset, path)
        elif path.suffix.lower() == ".csv":
            self._save_csv(dataset, path)
        else:
            raise ValueError(f"Unsupported format: {path.suffix}")

    def _save_jsonl(self, dataset: TestDataset, path: Path) -> None:
        """Save as JSONL."""
        with open(path, "w", encoding="utf-8") as f:
            for case in dataset.cases:
                data = {
                    "case_id": case.case_id,
                    "input": case.input,
                    "expected_behavior": case.expected_behavior,
                }
                if case.command:
                    data["command"] = case.command
                if case.expected_skill:
                    data["expected_skill"] = case.expected_skill
                if case.expected_output_contains:
                    data["expected_output_contains"] = case.expected_output_contains
                if case.tags:
                    data["tags"] = case.tags
                if case.context_files:
                    data["context_files"] = case.context_files
                if case.conversation_history:
                    data["conversation_history"] = [
                        {"role": m.role, "content": m.content}
                        for m in case.conversation_history
                    ]
                if case.project_config:
                    data["project_config"] = case.project_config.model_dump()

                f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _save_csv(self, dataset: TestDataset, path: Path) -> None:
        """Save as CSV."""
        fieldnames = [
            "case_id",
            "input",
            "command",
            "expected_skill",
            "expected_output_contains",
            "expected_behavior",
            "tags",
            "context_files",
        ]

        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for case in dataset.cases:
                writer.writerow(
                    {
                        "case_id": case.case_id,
                        "input": case.input,
                        "command": case.command or "",
                        "expected_skill": case.expected_skill or "",
                        "expected_output_contains": json.dumps(
                            case.expected_output_contains, ensure_ascii=False
                        ),
                        "expected_behavior": case.expected_behavior,
                        "tags": json.dumps(case.tags, ensure_ascii=False),
                        "context_files": json.dumps(
                            case.context_files, ensure_ascii=False
                        ),
                    }
                )
