"""Unit tests for DatasetService."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meta_agent.services.dataset_service import DatasetService, DatasetValidationError


class TestDatasetService:
    """Tests for DatasetService."""

    @pytest.fixture
    def service(self, temp_dir: Path) -> DatasetService:
        """Create a dataset service instance."""
        # Create test-resources structure
        datasets_dir = temp_dir / "test-resources" / "datasets"
        files_dir = temp_dir / "test-resources" / "files"
        datasets_dir.mkdir(parents=True)
        files_dir.mkdir(parents=True)

        return DatasetService(str(temp_dir))

    def test_load_dataset_jsonl(self, service: DatasetService, temp_dir: Path):
        """Test loading JSONL dataset."""
        # Create test dataset
        dataset_file = temp_dir / "test-resources" / "datasets" / "test.jsonl"
        cases = [
            {
                "case_id": "test_001",
                "input": "/test command",
                "expected_behavior": "Should work",
            },
            {
                "case_id": "test_002",
                "input": "/another command",
                "expected_behavior": "Should also work",
            },
        ]
        with open(dataset_file, "w") as f:
            for case in cases:
                f.write(json.dumps(case) + "\n")

        # Load dataset
        dataset = service.load_dataset(str(dataset_file))

        assert dataset.name == "test"
        assert len(dataset.cases) == 2
        assert dataset.cases[0].case_id == "test_001"
        assert dataset.cases[1].case_id == "test_002"

    def test_load_dataset_csv(self, service: DatasetService, temp_dir: Path):
        """Test loading CSV dataset."""
        dataset_file = temp_dir / "test-resources" / "datasets" / "test.csv"
        with open(dataset_file, "w") as f:
            f.write("case_id,input,expected_behavior\n")
            f.write('test_001,/test command,Should work\n')
            f.write('test_002,/another,Should also work\n')

        dataset = service.load_dataset(str(dataset_file))

        assert len(dataset.cases) == 2
        assert dataset.cases[0].input == "/test command"

    def test_load_dataset_validation_error_empty(self, service: DatasetService, temp_dir: Path):
        """Test validation error for empty dataset."""
        dataset_file = temp_dir / "test-resources" / "datasets" / "empty.jsonl"
        dataset_file.touch()

        with pytest.raises(DatasetValidationError) as exc_info:
            service.load_dataset(str(dataset_file))

        assert "at least one test case" in str(exc_info.value.errors[0])

    def test_load_dataset_validation_error_duplicate_ids(
        self, service: DatasetService, temp_dir: Path
    ):
        """Test validation error for duplicate case IDs."""
        dataset_file = temp_dir / "test-resources" / "datasets" / "dups.jsonl"
        cases = [
            {"case_id": "same_id", "input": "/cmd1", "expected_behavior": "a"},
            {"case_id": "same_id", "input": "/cmd2", "expected_behavior": "b"},
        ]
        with open(dataset_file, "w") as f:
            for case in cases:
                f.write(json.dumps(case) + "\n")

        with pytest.raises(DatasetValidationError) as exc_info:
            service.load_dataset(str(dataset_file))

        assert "Duplicate" in str(exc_info.value.errors[0])

    def test_load_dataset_with_context_files(self, service: DatasetService, temp_dir: Path):
        """Test loading dataset with context files."""
        # Create context file
        files_dir = temp_dir / "test-resources" / "files"
        (files_dir / "data.csv").touch()

        dataset_file = temp_dir / "test-resources" / "datasets" / "test.jsonl"
        case = {
            "case_id": "test_001",
            "input": "/analyze",
            "expected_behavior": "Analyze data",
            "context_files": ["data.csv"],
        }
        with open(dataset_file, "w") as f:
            f.write(json.dumps(case) + "\n")

        dataset = service.load_dataset(str(dataset_file))

        assert dataset.cases[0].context_files == ["data.csv"]

    def test_load_dataset_missing_context_file(self, service: DatasetService, temp_dir: Path):
        """Test validation error for missing context file."""
        dataset_file = temp_dir / "test-resources" / "datasets" / "test.jsonl"
        case = {
            "case_id": "test_001",
            "input": "/analyze",
            "expected_behavior": "Analyze",
            "context_files": ["missing.csv"],
        }
        with open(dataset_file, "w") as f:
            f.write(json.dumps(case) + "\n")

        with pytest.raises(DatasetValidationError) as exc_info:
            service.load_dataset(str(dataset_file))

        assert "not found" in str(exc_info.value.errors[0])

    def test_get_test_files(self, service: DatasetService, temp_dir: Path):
        """Test getting test files from dataset."""
        # Create files
        files_dir = temp_dir / "test-resources" / "files"
        (files_dir / "file1.csv").write_text("data")
        (files_dir / "file2.xlsx").write_text("data")

        dataset_file = temp_dir / "test-resources" / "datasets" / "test.jsonl"
        case = {
            "case_id": "test_001",
            "input": "/test",
            "expected_behavior": "Test",
            "context_files": ["file1.csv", "file2.xlsx"],
        }
        with open(dataset_file, "w") as f:
            f.write(json.dumps(case) + "\n")

        dataset = service.load_dataset(str(dataset_file))
        files = service.get_test_files(dataset)

        assert len(files) == 2
        assert any(f.relative_path == "file1.csv" for f in files)
        assert any(f.relative_path == "file2.xlsx" for f in files)

    def test_save_dataset_jsonl(self, service: DatasetService, temp_dir: Path):
        """Test saving dataset as JSONL."""
        from meta_agent.models.dataset import TestDataset, TestCase

        dataset = TestDataset(
            name="test-save",
            plugin_name="test-plugin",
            cases=[
                TestCase(
                    case_id="save_001",
                    input="/save test",
                    expected_behavior="Should save",
                ),
            ],
        )

        output_path = temp_dir / "output.jsonl"
        service.save_dataset(dataset, str(output_path))

        # Verify
        with open(output_path) as f:
            data = json.loads(f.readline())

        assert data["case_id"] == "save_001"
        assert data["input"] == "/save test"
