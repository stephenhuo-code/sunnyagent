"""Unit tests for SunnyAgentClient."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from meta_agent.services.sunnyagent_client import (
    SunnyAgentClient,
    SunnyAgentError,
    AuthenticationError,
    UploadError,
    Project,
    FileInfo,
    Conversation,
)


class TestSunnyAgentClient:
    """Tests for SunnyAgentClient."""

    @pytest.fixture
    def client(self) -> SunnyAgentClient:
        """Create a SunnyAgentClient instance."""
        return SunnyAgentClient(
            base_url="http://localhost:8008",
            admin_username="admin",
            admin_password="password123",
        )

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx client."""
        mock = MagicMock()
        mock.post = AsyncMock()
        mock.get = AsyncMock()
        mock.delete = AsyncMock()
        mock.aclose = AsyncMock()
        return mock

    # Project Operations Tests

    @pytest.mark.asyncio
    async def test_create_project_success(self, client: SunnyAgentClient, mock_httpx_client):
        """Test creating a project successfully."""
        mock_httpx_client.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "id": "proj-123",
                "name": "test-project",
                "description": "Test description",
            },
        )

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            project = await client.create_project(
                name="test-project",
                description="Test description",
            )

        assert project.id == "proj-123"
        assert project.name == "test-project"

    @pytest.mark.asyncio
    async def test_get_project_success(self, client: SunnyAgentClient, mock_httpx_client):
        """Test getting a project by name."""
        mock_httpx_client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {"id": "proj-123", "name": "test-project", "description": "Test"},
                {"id": "proj-456", "name": "other-project", "description": "Other"},
            ],
        )

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            project = await client.get_project("test-project")

        assert project is not None
        assert project.id == "proj-123"
        assert project.name == "test-project"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, client: SunnyAgentClient, mock_httpx_client):
        """Test getting a non-existent project."""
        mock_httpx_client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: [],
        )

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            project = await client.get_project("non-existent")

        assert project is None

    @pytest.mark.asyncio
    async def test_delete_project_success(self, client: SunnyAgentClient, mock_httpx_client):
        """Test deleting a project."""
        mock_httpx_client.delete.return_value = MagicMock(status_code=200)

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            await client.delete_project("proj-123")

        mock_httpx_client.delete.assert_called_once()

    # File Upload/Download Tests

    @pytest.mark.asyncio
    async def test_upload_file_success(self, client: SunnyAgentClient, mock_httpx_client, tmp_path):
        """Test uploading a file successfully."""
        # Create a test file
        test_file = tmp_path / "test.csv"
        test_file.write_text("col1,col2\n1,2\n")

        mock_httpx_client.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "id": "file-123",
                "name": "test.csv",
                "size": 15,
                "content_type": "text/csv",
            },
        )

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            file_info = await client.upload_file(
                project_id="proj-123",
                file_path=str(test_file),
            )

        assert file_info.id == "file-123"
        assert file_info.name == "test.csv"

    @pytest.mark.asyncio
    async def test_get_project_files_success(self, client: SunnyAgentClient, mock_httpx_client):
        """Test getting project files."""
        mock_httpx_client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {"id": "file-1", "name": "data.csv", "size": 100, "content_type": "text/csv"},
                {"id": "file-2", "name": "report.xlsx", "size": 200, "content_type": "application/vnd.ms-excel"},
            ],
        )

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            files = await client.get_project_files("proj-123")

        assert len(files) == 2
        assert files[0].name == "data.csv"
        assert files[1].name == "report.xlsx"

    @pytest.mark.asyncio
    async def test_upload_file_not_found(self, client: SunnyAgentClient):
        """Test uploading a non-existent file raises error."""
        with pytest.raises(UploadError):
            await client.upload_file(
                project_id="proj-123",
                file_path="/non/existent/file.csv",
            )

    # Authentication Tests

    @pytest.mark.asyncio
    async def test_login_success(self, client: SunnyAgentClient, mock_httpx_client):
        """Test successful login."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.cookies = {"access_token": "jwt-token-123"}
        mock_httpx_client.post.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            await client.login()

        # Verify cookies were stored
        assert "access_token" in client._cookies

    @pytest.mark.asyncio
    async def test_login_failure(self, client: SunnyAgentClient, mock_httpx_client):
        """Test login failure raises AuthenticationError."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid credentials"
        mock_httpx_client.post.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            with pytest.raises(AuthenticationError):
                await client.login()

    # Conversation Tests

    @pytest.mark.asyncio
    async def test_create_conversation_success(self, client: SunnyAgentClient, mock_httpx_client):
        """Test creating a conversation."""
        mock_httpx_client.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "id": "conv-123",
                "project_id": "proj-123",
                "thread_id": "thread-123",
                "title": "Test Chat",
            },
        )

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            conversation = await client.create_conversation(
                project_id="proj-123",
                title="Test Chat",
            )

        assert conversation.id == "conv-123"
        assert conversation.thread_id == "thread-123"

    @pytest.mark.asyncio
    async def test_get_conversation_success(self, client: SunnyAgentClient, mock_httpx_client):
        """Test getting a conversation."""
        mock_httpx_client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "id": "conv-123",
                "project_id": "proj-123",
                "thread_id": "thread-123",
                "title": "Test Chat",
            },
        )

        with patch.object(client, "_get_client", return_value=mock_httpx_client):
            conversation = await client.get_conversation("conv-123")

        assert conversation is not None
        assert conversation.id == "conv-123"

    @pytest.mark.asyncio
    async def test_close_client(self, client: SunnyAgentClient, mock_httpx_client):
        """Test closing the client."""
        client._client = mock_httpx_client

        await client.close()

        mock_httpx_client.aclose.assert_called_once()
        assert client._client is None
