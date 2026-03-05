"""Integration tests for LangfuseClient.

These tests require a running Langfuse instance.
Set LANGFUSE_BASE_URL, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY environment variables.
"""

from __future__ import annotations

import os
import pytest

from meta_agent.services.langfuse_client import LangfuseClient


# Skip all tests if Langfuse is not configured
pytestmark = pytest.mark.skipif(
    not os.environ.get("LANGFUSE_PUBLIC_KEY"),
    reason="Langfuse not configured (LANGFUSE_PUBLIC_KEY not set)",
)


class TestLangfuseClientIntegration:
    """Integration tests for LangfuseClient."""

    @pytest.fixture
    def client(self) -> LangfuseClient:
        """Create a LangfuseClient instance."""
        return LangfuseClient(
            base_url=os.environ.get("LANGFUSE_BASE_URL", "http://localhost:3001"),
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
        )

    @pytest.mark.asyncio
    async def test_create_dataset(self, client: LangfuseClient):
        """Test creating a dataset in Langfuse."""
        dataset = await client.create_dataset(
            name="meta-agent-test-dataset",
            description="Test dataset for integration tests",
        )
        assert dataset.name == "meta-agent-test-dataset"
        assert dataset.id is not None

    @pytest.mark.asyncio
    async def test_create_dataset_item(self, client: LangfuseClient):
        """Test creating a dataset item."""
        # First create a dataset
        dataset = await client.create_dataset(
            name="meta-agent-test-items",
            description="Test dataset for item creation",
        )

        # Then create an item
        item = await client.create_dataset_item(
            dataset_name=dataset.name,
            input_data={"input": "/test command"},
            expected_output={"expected_behavior": "Test behavior"},
            metadata={"case_id": "test_001"},
        )
        assert item.id is not None

    @pytest.mark.asyncio
    async def test_get_traces(self, client: LangfuseClient):
        """Test getting traces from Langfuse."""
        traces = await client.get_traces(limit=10)
        # Just verify the call succeeds and returns a list
        assert isinstance(traces, list)

    @pytest.mark.asyncio
    async def test_add_score(self, client: LangfuseClient):
        """Test adding a score to a trace."""
        # Get some traces first
        traces = await client.get_traces(limit=1)
        if not traces:
            pytest.skip("No traces available for scoring test")

        trace = traces[0]
        await client.add_score(
            trace_id=trace.id,
            name="test_score",
            value=0.85,
            comment="Test score from integration test",
        )
        # If no exception, test passed
