"""
Langfuse Admin API Client - 用户账号同步

基于 Langfuse SCIM-compliant API 实现用户管理：
- 创建用户
- 禁用用户（从组织移除）
- 删除用户
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LangfuseUser:
    """Langfuse 用户信息"""
    id: str
    user_name: str
    display_name: str
    email: str
    active: bool


class LangfuseAdminClient:
    """
    Langfuse Admin API 客户端

    用于 SunnyAgent 与 Langfuse 之间的用户账号同步。
    使用组织级 API 密钥进行认证。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        org_public_key: Optional[str] = None,
        org_secret_key: Optional[str] = None
    ):
        self._base_url = base_url or os.getenv("LANGFUSE_BASE_URL", "http://localhost:3001")
        self._org_public_key = org_public_key or os.getenv("LANGFUSE_ORG_PUBLIC_KEY")
        self._org_secret_key = org_secret_key or os.getenv("LANGFUSE_ORG_SECRET_KEY")

        if not self._org_public_key or not self._org_secret_key:
            logger.warning("Langfuse organization API keys not configured, user sync disabled")

    @property
    def enabled(self) -> bool:
        """Admin API 是否可用"""
        return bool(self._org_public_key and self._org_secret_key)

    def _get_auth(self) -> tuple:
        """获取 Basic Auth 认证信息"""
        return (self._org_public_key, self._org_secret_key)

    async def health_check(self) -> bool:
        """检查 Langfuse 服务是否可用"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/api/public/health")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Langfuse health check failed: {e}")
            return False

    async def list_users(self) -> list[LangfuseUser]:
        """
        列出组织中的所有用户

        Returns:
            用户列表
        """
        if not self.enabled:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self._base_url}/api/public/scim/Users",
                    auth=self._get_auth()
                )
                response.raise_for_status()
                data = response.json()

                users = []
                for resource in data.get("Resources", []):
                    emails = resource.get("emails", [])
                    primary_email = next(
                        (e["value"] for e in emails if e.get("primary")),
                        emails[0]["value"] if emails else ""
                    )
                    users.append(LangfuseUser(
                        id=resource["id"],
                        user_name=resource.get("userName", ""),
                        display_name=resource.get("displayName", ""),
                        email=primary_email,
                        active=resource.get("active", True)
                    ))
                return users

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to list Langfuse users: HTTP {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Failed to list Langfuse users: {e}")
            return []

    async def create_user(self, email: str, display_name: str) -> Optional[LangfuseUser]:
        """
        在 Langfuse 中创建用户

        Args:
            email: 用户邮箱（作为用户名）
            display_name: 显示名称

        Returns:
            创建的用户信息，失败返回 None
        """
        if not self.enabled:
            logger.warning("Langfuse Admin API not configured, skipping user creation")
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self._base_url}/api/public/scim/Users",
                    auth=self._get_auth(),
                    json={
                        "userName": email,
                        "displayName": display_name,
                        "emails": [{"value": email, "primary": True}]
                    }
                )
                response.raise_for_status()
                data = response.json()

                logger.info(f"Created Langfuse user: {email}")
                return LangfuseUser(
                    id=data["id"],
                    user_name=data.get("userName", email),
                    display_name=data.get("displayName", display_name),
                    email=email,
                    active=data.get("active", True)
                )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                logger.info(f"Langfuse user already exists: {email}")
                # 用户已存在，尝试查找
                users = await self.list_users()
                for user in users:
                    if user.email == email:
                        return user
            else:
                logger.error(f"Failed to create Langfuse user {email}: HTTP {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Failed to create Langfuse user {email}: {e}")
            return None

    async def disable_user(self, langfuse_user_id: str) -> bool:
        """
        禁用 Langfuse 用户（从组织中移除）

        Args:
            langfuse_user_id: Langfuse 用户 ID

        Returns:
            是否成功
        """
        if not self.enabled:
            logger.warning("Langfuse Admin API not configured, skipping user disable")
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(
                    f"{self._base_url}/api/public/scim/Users/{langfuse_user_id}",
                    auth=self._get_auth()
                )
                # 204 No Content 表示成功
                if response.status_code in (200, 204):
                    logger.info(f"Disabled Langfuse user: {langfuse_user_id}")
                    return True
                else:
                    logger.error(f"Failed to disable Langfuse user: HTTP {response.status_code}")
                    return False

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Langfuse user not found: {langfuse_user_id}")
                return True  # 用户不存在视为已禁用
            logger.error(f"Failed to disable Langfuse user {langfuse_user_id}: HTTP {e.response.status_code}")
            return False
        except Exception as e:
            logger.error(f"Failed to disable Langfuse user {langfuse_user_id}: {e}")
            return False

    async def delete_user(self, langfuse_user_id: str) -> bool:
        """
        删除 Langfuse 用户（与 disable_user 相同，从组织中移除）

        Args:
            langfuse_user_id: Langfuse 用户 ID

        Returns:
            是否成功
        """
        # SCIM API 的 DELETE 操作是从组织中移除用户
        return await self.disable_user(langfuse_user_id)

    async def get_user(self, langfuse_user_id: str) -> Optional[LangfuseUser]:
        """
        获取 Langfuse 用户信息

        Args:
            langfuse_user_id: Langfuse 用户 ID

        Returns:
            用户信息，不存在返回 None
        """
        if not self.enabled:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self._base_url}/api/public/scim/Users/{langfuse_user_id}",
                    auth=self._get_auth()
                )
                response.raise_for_status()
                data = response.json()

                emails = data.get("emails", [])
                primary_email = next(
                    (e["value"] for e in emails if e.get("primary")),
                    emails[0]["value"] if emails else ""
                )
                return LangfuseUser(
                    id=data["id"],
                    user_name=data.get("userName", ""),
                    display_name=data.get("displayName", ""),
                    email=primary_email,
                    active=data.get("active", True)
                )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Failed to get Langfuse user {langfuse_user_id}: HTTP {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Failed to get Langfuse user {langfuse_user_id}: {e}")
            return None


# 全局单例
_admin_client: Optional[LangfuseAdminClient] = None


def get_langfuse_admin_client() -> LangfuseAdminClient:
    """获取 LangfuseAdminClient 单例"""
    global _admin_client
    if _admin_client is None:
        _admin_client = LangfuseAdminClient()
    return _admin_client


def reset_langfuse_admin_client():
    """重置 LangfuseAdminClient 单例（用于测试）"""
    global _admin_client
    _admin_client = None
