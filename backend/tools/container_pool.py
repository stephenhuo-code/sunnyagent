"""
容器池管理器 - 预热容器以实现 ~10-50ms 执行响应
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import docker

logger = logging.getLogger(__name__)

# 项目标识 - 用于 Docker Desktop 分组显示
PROJECT_NAME = "sunnyagent"
CONTAINER_LABELS = {
    "com.docker.compose.project": PROJECT_NAME,
    "com.docker.compose.service": "sandbox",
    "com.docker.compose.oneoff": "False",
}


@dataclass
class PooledContainer:
    """池化容器的状态"""

    container: docker.models.containers.Container
    created_at: datetime = field(default_factory=datetime.now)
    use_count: int = 0


class ContainerPool:
    """
    Docker 容器池

    启动时预热指定数量的容器，执行请求时从池中获取空闲容器，
    执行完成后归还到池中，避免每次创建/销毁容器的开销。
    """

    def __init__(
        self,
        image: str = "sunnyagent-sandbox:latest",
        pool_size: int = 5,
        max_uses_per_container: int = 100,
        mem_limit: str = "512m",
        cpu_quota: int = 100000,  # 1 CPU
    ):
        self.client = docker.from_env()
        self.image = image
        self.pool_size = pool_size
        self.max_uses = max_uses_per_container
        self.mem_limit = mem_limit
        self.cpu_quota = cpu_quota

        self._pool: asyncio.Queue[PooledContainer] = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._initialized = False
        self._total_created = 0
        self._all_containers: set[str] = set()  # 跟踪所有创建的容器ID

    async def initialize(self) -> None:
        """启动时预热容器池"""
        async with self._lock:
            if self._initialized:
                return

            # 清理上次运行遗留的容器
            await self.cleanup_all_project_containers()

            logger.info(f"Initializing container pool with {self.pool_size} containers...")

            for i in range(self.pool_size):
                try:
                    pooled = await self._create_container()
                    await self._pool.put(pooled)
                    logger.info(f"Container {i + 1}/{self.pool_size} ready")
                except Exception as e:
                    logger.error(f"Failed to create container {i + 1}: {e}")
                    raise

            self._initialized = True
            logger.info("Container pool initialized successfully")

    async def _create_container(self) -> PooledContainer:
        """创建新的池化容器"""
        loop = asyncio.get_event_loop()
        container_name = f"{PROJECT_NAME}-sandbox-{self._total_created + 1}"

        # 清理同名旧容器（如果存在）
        try:
            existing = await loop.run_in_executor(
                None, lambda: self.client.containers.get(container_name)
            )
            await loop.run_in_executor(None, lambda: existing.remove(force=True))
        except docker.errors.NotFound:
            pass

        container = await loop.run_in_executor(
            None,
            lambda: self.client.containers.run(
                self.image,
                name=container_name,  # 命名容器
                labels=CONTAINER_LABELS,  # 添加标签用于分组
                detach=True,
                mem_limit=self.mem_limit,
                cpu_quota=self.cpu_quota,
                network_disabled=True,  # 禁用网络访问
                cap_drop=["ALL"],  # 移除所有 Linux capabilities
                security_opt=["no-new-privileges"],  # 禁止提权
            ),
        )
        self._all_containers.add(container.id)
        self._total_created += 1
        return PooledContainer(container=container)

    async def acquire(self, timeout: float = 30.0) -> PooledContainer:
        """
        从池中获取一个空闲容器

        Args:
            timeout: 等待超时时间（秒）

        Returns:
            PooledContainer 实例
        """
        try:
            pooled = await asyncio.wait_for(self._pool.get(), timeout=timeout)
            pooled.use_count += 1
            return pooled
        except asyncio.TimeoutError:
            logger.warning("Pool exhausted, creating temporary container")
            return await self._create_container()

    async def release(self, pooled: PooledContainer) -> None:
        """
        将容器归还到池中

        如果容器使用次数超过限制，则销毁并创建新容器
        """
        # 检查是否需要替换
        if pooled.use_count >= self.max_uses:
            logger.info(f"Container reached {self.max_uses} uses, replacing...")
            await self._destroy_container(pooled)
            pooled = await self._create_container()

        # 清理容器输出目录
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: pooled.container.exec_run(["rm", "-rf", "/output/*"]),
            )
        except Exception as e:
            logger.warning(f"Failed to clean output dir: {e}")

        await self._pool.put(pooled)

    async def _destroy_container(self, pooled: PooledContainer) -> None:
        """安全销毁容器"""
        container_id = pooled.container.id
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: pooled.container.stop(timeout=5))
            await loop.run_in_executor(None, lambda: pooled.container.remove(force=True))
        except Exception as e:
            logger.error(f"Error destroying container: {e}")
        finally:
            self._all_containers.discard(container_id)

    async def cleanup_all_project_containers(self) -> None:
        """清理所有 sandbox 容器（保留 postgres 等其他服务）"""
        logger.info("Cleaning up all sunnyagent sandbox containers...")
        loop = asyncio.get_event_loop()

        try:
            containers = await loop.run_in_executor(
                None,
                lambda: self.client.containers.list(
                    all=True,
                    filters={
                        "label": [
                            f"com.docker.compose.project={PROJECT_NAME}",
                            "com.docker.compose.service=sandbox",
                        ]
                    }
                )
            )

            for container in containers:
                try:
                    logger.info(f"Removing container: {container.name}")
                    await loop.run_in_executor(None, lambda c=container: c.remove(force=True))
                except Exception as e:
                    logger.warning(f"Failed to remove {container.name}: {e}")

            logger.info(f"Cleaned up {len(containers)} containers")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def shutdown(self) -> None:
        """关闭池中所有容器"""
        logger.info("Shutting down container pool...")

        # 先清空队列
        while not self._pool.empty():
            try:
                await asyncio.wait_for(self._pool.get(), timeout=1.0)
            except asyncio.TimeoutError:
                break

        # 基于标签清理所有容器
        await self.cleanup_all_project_containers()

        self._all_containers.clear()
        self._initialized = False
        logger.info("Container pool shutdown complete")

    @property
    def stats(self) -> dict:
        """返回池状态统计"""
        return {
            "pool_size": self.pool_size,
            "available": self._pool.qsize(),
            "total_created": self._total_created,
            "initialized": self._initialized,
        }


# ============================================
# 全局单例
# ============================================
_pool: Optional[ContainerPool] = None


async def get_pool() -> ContainerPool:
    """获取全局容器池单例"""
    global _pool
    if _pool is None:
        _pool = ContainerPool()
        await _pool.initialize()
    return _pool


async def shutdown_pool() -> None:
    """关闭全局容器池"""
    global _pool
    if _pool is not None:
        await _pool.shutdown()
        _pool = None


async def cleanup_all_sunnyagent_containers() -> None:
    """独立清理函数，可在池未初始化时调用（只清理 sandbox 容器）"""
    client = docker.from_env()
    try:
        containers = client.containers.list(
            all=True,
            filters={
                "label": [
                    f"com.docker.compose.project={PROJECT_NAME}",
                    "com.docker.compose.service=sandbox",
                ]
            }
        )
        for container in containers:
            try:
                logger.info(f"Force removing container: {container.name}")
                container.remove(force=True)
            except Exception as e:
                logger.warning(f"Failed to remove {container.name}: {e}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
