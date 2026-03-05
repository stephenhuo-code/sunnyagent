"""Integration tests for SunnyAgentClient.

These tests require a running SunnyAgent instance.
Set SUNNYAGENT_BASE_URL, SUNNYAGENT_USERNAME, SUNNYAGENT_PASSWORD environment variables.
"""

from __future__ import annotations

import os
import pytest

from meta_agent.services.sunnyagent_client import SunnyAgentClient


# Skip all tests if SunnyAgent is not configured
pytestmark = pytest.mark.skipif(
    not os.environ.get("SUNNYAGENT_USERNAME"),
    reason="SunnyAgent not configured (SUNNYAGENT_USERNAME not set)",
)


class TestSunnyAgentClientIntegration:
    """Integration tests for SunnyAgentClient."""

    @pytest.fixture
    def client(self) -> SunnyAgentClient:
        """Create a SunnyAgentClient instance."""
        return SunnyAgentClient(
            base_url=os.environ.get("SUNNYAGENT_BASE_URL", "http://localhost:8008"),
            username=os.environ.get("SUNNYAGENT_USERNAME", "admin"),
            password=os.environ.get("SUNNYAGENT_PASSWORD", ""),
        )

    @pytest.mark.asyncio
    async def test_login(self, client: SunnyAgentClient):
        """Test login to SunnyAgent."""
        await client.login()
        assert client._token is not None

    @pytest.mark.asyncio
    async def test_create_project(self, client: SunnyAgentClient):
        """Test creating a project."""
        await client.login()
        project = await client.create_project(
            name="meta-agent-test-project",
            description="Test project for integration tests",
        )
        assert project.name == "meta-agent-test-project"
        assert project.id is not None

        # Cleanup
        await client.delete_project(project.id)

    @pytest.mark.asyncio
    async def test_create_conversation(self, client: SunnyAgentClient):
        """Test creating a conversation."""
        await client.login()
        conversation = await client.create_conversation(
            title="Test Conversation",
        )
        assert conversation.id is not None

    @pytest.mark.asyncio
    async def test_send_message_and_wait(self, client: SunnyAgentClient):
        """Test sending a message and waiting for response."""
        await client.login()

        # Create a conversation first
        conversation = await client.create_conversation(
            title="Test Chat",
        )

        # Send a simple message
        response = await client.send_message_and_wait(
            thread_id=conversation.id,
            message="Hello, this is a test message.",
            timeout=30.0,
        )
        assert response.response is not None
        assert len(response.response) > 0

    @pytest.mark.asyncio
    async def test_file_upload(self, client: SunnyAgentClient, tmp_path):
        """Test uploading a file."""
        await client.login()

        # Create a test file
        test_file = tmp_path / "test.csv"
        test_file.write_text("col1,col2\n1,2\n3,4\n")

        # Create a project for the file
        project = await client.create_project(
            name="meta-agent-file-test",
            description="Test project for file upload",
        )

        try:
            file_info = await client.upload_file(
                project_id=project.id,
                file_path=str(test_file),
            )
            assert file_info.id is not None
            assert file_info.filename == "test.csv"
        finally:
            # Cleanup
            await client.delete_project(project.id)

    @pytest.mark.asyncio
    async def test_get_project_files(self, client: SunnyAgentClient, tmp_path):
        """Test getting project files."""
        await client.login()

        # Create a project
        project = await client.create_project(
            name="meta-agent-files-test",
            description="Test project for file listing",
        )

        try:
            # Upload a file
            test_file = tmp_path / "data.csv"
            test_file.write_text("a,b\n1,2\n")
            await client.upload_file(
                project_id=project.id,
                file_path=str(test_file),
            )

            # List files
            files = await client.get_project_files(project.id)
            assert len(files) >= 1
            assert any(f.filename == "data.csv" for f in files)
        finally:
            # Cleanup
            await client.delete_project(project.id)
