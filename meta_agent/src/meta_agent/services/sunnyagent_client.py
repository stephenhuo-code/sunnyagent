"""SunnyAgent API client for test execution."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator

import httpx

logger = logging.getLogger(__name__)


# Data Types


@dataclass
class Project:
    """Project."""

    id: str
    name: str
    description: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class FileInfo:
    """File information."""

    id: str
    name: str
    size: int = 0
    content_type: str = ""
    uploaded_at: datetime = field(default_factory=datetime.now)


@dataclass
class Conversation:
    """Conversation."""

    id: str
    project_id: str
    thread_id: str
    title: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SSEEvent:
    """SSE event."""

    event: str  # message, tool_call, error, done
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    """Chat response."""

    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    agent_used: str | None = None
    skill_used: str | None = None
    langfuse_trace_id: str | None = None


# Exceptions


class SunnyAgentError(Exception):
    """SunnyAgent operation error."""

    pass


class AuthenticationError(SunnyAgentError):
    """Authentication error."""

    pass


class ProjectExistsError(SunnyAgentError):
    """Project already exists."""

    pass


class FileTooLargeError(SunnyAgentError):
    """File too large (max 10MB)."""

    pass


class UploadError(SunnyAgentError):
    """Upload error."""

    pass


class ChatTimeoutError(SunnyAgentError):
    """Chat timeout."""

    pass


class SunnyAgentClient:
    """SunnyAgent API client.

    Handles:
    - Authentication
    - Project management
    - File uploads
    - Conversation management
    - Chat interactions
    """

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def __init__(
        self,
        base_url: str = "http://localhost:8008",
        admin_username: str = "admin",
        admin_password: str = "",
    ):
        """
        Initialize SunnyAgent client.

        Args:
            base_url: SunnyAgent API base URL
            admin_username: Admin username
            admin_password: Admin password
        """
        self.base_url = base_url.rstrip("/")
        self.admin_username = admin_username
        self.admin_password = admin_password
        self._client: httpx.AsyncClient | None = None
        self._cookies: dict[str, str] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(60.0),
                cookies=self._cookies,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # Authentication

    async def login(self) -> None:
        """
        Login with admin account.

        Raises:
            AuthenticationError: If login fails
        """
        client = await self._get_client()
        try:
            response = await client.post(
                "/api/auth/login",
                json={
                    "username": self.admin_username,
                    "password": self.admin_password,
                },
            )
            if response.status_code != 200:
                raise AuthenticationError(
                    f"Login failed: {response.status_code} - {response.text}"
                )

            # Store cookies for subsequent requests
            self._cookies = dict(response.cookies)
            # Recreate client with cookies
            await self.close()
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(60.0),
                cookies=self._cookies,
            )
            logger.info(f"Logged in as {self.admin_username}")
        except httpx.RequestError as e:
            raise AuthenticationError(f"Login request failed: {e}")

    async def logout(self) -> None:
        """Logout."""
        client = await self._get_client()
        try:
            await client.post("/api/auth/logout")
            self._cookies = {}
        except httpx.RequestError:
            pass

    # Project Operations

    async def create_project(
        self,
        name: str,
        description: str | None = None,
    ) -> Project:
        """
        Create project.

        Args:
            name: Project name
            description: Project description

        Returns:
            project: Created project

        Raises:
            ProjectExistsError: If project already exists
        """
        client = await self._get_client()
        response = await client.post(
            "/api/projects",
            json={
                "name": name,
                "description": description or "",
            },
        )

        if response.status_code == 409:
            raise ProjectExistsError(f"Project '{name}' already exists")
        if response.status_code != 200 and response.status_code != 201:
            raise SunnyAgentError(
                f"Failed to create project: {response.status_code} - {response.text}"
            )

        data = response.json()
        return Project(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
        )

    async def get_project(self, name: str) -> Project | None:
        """
        Get project by name.

        Returns:
            project: Project or None
        """
        client = await self._get_client()
        response = await client.get("/api/projects")

        if response.status_code != 200:
            return None

        projects = response.json()
        for p in projects:
            if p["name"] == name:
                return Project(
                    id=p["id"],
                    name=p["name"],
                    description=p.get("description"),
                    created_at=datetime.fromisoformat(p["created_at"])
                    if "created_at" in p
                    else datetime.now(),
                )
        return None

    async def delete_project(self, project_id: str) -> None:
        """Delete project."""
        client = await self._get_client()
        response = await client.delete(f"/api/projects/{project_id}")
        if response.status_code not in (200, 204):
            raise SunnyAgentError(f"Failed to delete project: {response.text}")

    # File Operations

    async def upload_file(
        self,
        project_id: str,
        file_path: str,
        file_name: str | None = None,
    ) -> FileInfo:
        """
        Upload file to project.

        Args:
            project_id: Project ID
            file_path: Local file path
            file_name: Upload filename (optional)

        Returns:
            file_info: File information

        Raises:
            FileTooLargeError: If file exceeds 10MB
            UploadError: If upload fails
        """
        import os
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise UploadError(f"File not found: {file_path}")

        file_size = path.stat().st_size
        if file_size > self.MAX_FILE_SIZE:
            raise FileTooLargeError(
                f"File size {file_size} exceeds maximum {self.MAX_FILE_SIZE}"
            )

        name = file_name or path.name
        content_type = self._guess_content_type(name)

        client = await self._get_client()
        with open(file_path, "rb") as f:
            files = {"file": (name, f, content_type)}
            response = await client.post(
                f"/api/projects/{project_id}/files",
                files=files,
            )

        if response.status_code not in (200, 201):
            raise UploadError(
                f"Failed to upload file: {response.status_code} - {response.text}"
            )

        data = response.json()
        return FileInfo(
            id=data["id"],
            name=data.get("name", name),
            size=data.get("size", file_size),
            content_type=data.get("content_type", content_type),
            uploaded_at=datetime.fromisoformat(data["uploaded_at"])
            if "uploaded_at" in data
            else datetime.now(),
        )

    async def get_project_files(self, project_id: str) -> list[FileInfo]:
        """Get all files in project."""
        client = await self._get_client()
        response = await client.get(f"/api/projects/{project_id}/files")

        if response.status_code != 200:
            return []

        files = []
        for f in response.json():
            files.append(
                FileInfo(
                    id=f["id"],
                    name=f.get("name", ""),
                    size=f.get("size", 0),
                    content_type=f.get("content_type", ""),
                    uploaded_at=datetime.fromisoformat(f["uploaded_at"])
                    if "uploaded_at" in f
                    else datetime.now(),
                )
            )
        return files

    # Conversation Operations

    async def create_conversation(
        self,
        project_id: str,
        title: str | None = None,
    ) -> Conversation:
        """
        Create conversation.

        Args:
            project_id: Project ID
            title: Conversation title

        Returns:
            conversation: Created conversation
        """
        client = await self._get_client()
        response = await client.post(
            "/api/conversations",
            json={
                "project_id": project_id,
                "title": title or "Meta-Agent Test",
            },
        )

        if response.status_code not in (200, 201):
            raise SunnyAgentError(
                f"Failed to create conversation: {response.status_code} - {response.text}"
            )

        data = response.json()
        return Conversation(
            id=data["id"],
            project_id=data.get("project_id", project_id),
            thread_id=data.get("thread_id", data["id"]),
            title=data.get("title"),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
        )

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        """Get conversation details."""
        client = await self._get_client()
        response = await client.get(f"/api/conversations/{conversation_id}")

        if response.status_code != 200:
            return None

        data = response.json()
        return Conversation(
            id=data["id"],
            project_id=data.get("project_id", ""),
            thread_id=data.get("thread_id", data["id"]),
            title=data.get("title"),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
        )

    # Chat Operations

    async def send_message(
        self,
        thread_id: str,
        message: str,
        file_ids: list[str] | None = None,
        command: str | None = None,
    ) -> AsyncIterator[SSEEvent]:
        """
        Send message and get streaming response.

        Args:
            thread_id: Thread ID
            message: User message
            file_ids: Selected file IDs
            command: Direct command name (optional)

        Yields:
            event: SSE event

        Note:
            SunnyAgent automatically writes execution trace to Langfuse
        """
        client = await self._get_client()

        payload: dict[str, Any] = {
            "thread_id": thread_id,
            "message": message,
        }
        if file_ids:
            payload["file_ids"] = file_ids
        if command:
            payload["command"] = command

        async with client.stream(
            "POST",
            "/api/chat",
            json=payload,
            headers={"Accept": "text/event-stream"},
        ) as response:
            if response.status_code != 200:
                raise SunnyAgentError(
                    f"Chat failed: {response.status_code}"
                )

            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    try:
                        data = json.loads(line[5:].strip())
                        yield SSEEvent(event=event_type, data=data)
                    except json.JSONDecodeError:
                        pass

    async def send_message_and_wait(
        self,
        thread_id: str,
        message: str,
        file_ids: list[str] | None = None,
        timeout: float = 60.0,
    ) -> ChatResponse:
        """
        Send message and wait for complete response.

        Args:
            timeout: Timeout in seconds

        Returns:
            response: Complete response

        Raises:
            ChatTimeoutError: If timeout
        """
        content_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        agent_used: str | None = None
        skill_used: str | None = None
        trace_id: str | None = None

        try:
            async with asyncio.timeout(timeout):
                async for event in self.send_message(thread_id, message, file_ids):
                    if event.event == "message":
                        content = event.data.get("content", "")
                        if content:
                            content_parts.append(content)
                    elif event.event == "tool_call":
                        tool_calls.append(event.data)
                    elif event.event == "done":
                        trace_id = event.data.get("trace_id")
                        agent_used = event.data.get("agent")
                        skill_used = event.data.get("skill")
                    elif event.event == "error":
                        raise SunnyAgentError(
                            f"Chat error: {event.data.get('message', 'Unknown error')}"
                        )

        except asyncio.TimeoutError:
            raise ChatTimeoutError(f"Chat timed out after {timeout}s")

        return ChatResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            agent_used=agent_used,
            skill_used=skill_used,
            langfuse_trace_id=trace_id,
        )

    def _guess_content_type(self, filename: str) -> str:
        """Guess content type from filename."""
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        content_types = {
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xls": "application/vnd.ms-excel",
            "pdf": "application/pdf",
            "txt": "text/plain",
            "json": "application/json",
            "md": "text/markdown",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "doc": "application/msword",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
        }
        return content_types.get(ext, "application/octet-stream")
