"""
Langfuse Service - 可观测性平台集成

提供:
1. Langfuse 客户端初始化和健康检查
2. CallbackHandler 获取（用于 LangGraph 集成）
3. Token 用量统计查询
4. 优雅降级（Langfuse 不可用时不影响主流程）
"""

import os
import logging
from typing import Any, Literal, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


@dataclass
class LangfuseUserMapping:
    """SunnyAgent 用户与 Langfuse 用户的映射关系"""
    id: int
    sunnyagent_user_id: str
    langfuse_user_id: str
    langfuse_email: str
    status: str  # 'active' or 'disabled'
    created_at: datetime
    updated_at: datetime


class LangfuseService:
    """
    Langfuse 可观测性服务封装

    使用方式:
        service = LangfuseService()
        if service.enabled:
            handler = service.get_callback_handler()
            # 在 LangGraph 中使用 handler
    """

    def __init__(self):
        self._enabled = False
        self._client = None
        self._base_url = os.getenv("LANGFUSE_BASE_URL", "http://localhost:3001")
        self._sample_rate = float(os.getenv("LANGFUSE_SAMPLE_RATE", "1.0"))

        self._initialize()

    def _initialize(self):
        """初始化 Langfuse 客户端，失败时优雅降级"""
        # Check if tracing is explicitly disabled
        tracing_enabled = os.getenv("LANGFUSE_TRACING_ENABLED", "true").lower()
        if tracing_enabled in ("false", "0", "no", "off"):
            logger.info("Langfuse tracing disabled via LANGFUSE_TRACING_ENABLED=false")
            return

        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")

        if not public_key or not secret_key:
            logger.warning("Langfuse API keys not configured, tracing disabled")
            return

        try:
            from langfuse import get_client

            # 设置环境变量供 SDK 使用
            os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
            os.environ["LANGFUSE_SECRET_KEY"] = secret_key
            os.environ["LANGFUSE_HOST"] = self._base_url
            os.environ["LANGFUSE_SAMPLE_RATE"] = str(self._sample_rate)

            # 设置 OTEL Host（自托管 Langfuse 需要）
            # LiteLLM OTEL callback 使用此环境变量发送追踪数据
            os.environ["LANGFUSE_OTEL_HOST"] = self._base_url

            # 设置 LiteLLM OTEL callback（在 Langfuse SDK 初始化之前）
            # 这会自动追踪所有通过 LiteLLM/ChatLiteLLM 的 LLM 调用
            # 包括流式响应的 token 用量和模型名称
            try:
                import litellm
                litellm.callbacks = ["langfuse_otel"]
                logger.info("LiteLLM Langfuse OTEL callback enabled")
            except ImportError:
                logger.warning("litellm package not installed, OTEL callback not enabled")
            except Exception as e:
                logger.warning(f"Failed to enable LiteLLM OTEL callback: {e}")

            self._client = get_client()

            # 验证连接
            if self._client.auth_check():
                self._enabled = True
                logger.info(f"Langfuse connected successfully at {self._base_url}")
            else:
                logger.warning("Langfuse auth check failed, tracing disabled")

        except ImportError:
            logger.warning("langfuse package not installed, tracing disabled")
        except Exception as e:
            logger.warning(f"Langfuse initialization failed: {e}, tracing disabled")

    @property
    def enabled(self) -> bool:
        """Langfuse 是否可用"""
        return self._enabled

    @property
    def base_url(self) -> str:
        """Langfuse 服务地址（用于前端链接）"""
        return self._base_url

    @property
    def sample_rate(self) -> float:
        """Trace 采样率"""
        return self._sample_rate

    def get_callback_handler(self):
        """
        获取 LangChain/LangGraph CallbackHandler

        Returns:
            CallbackHandler 实例，如果 Langfuse 不可用则返回 None
        """
        if not self._enabled:
            return None

        try:
            from langfuse.langchain import CallbackHandler
            return CallbackHandler()
        except Exception as e:
            logger.warning(f"Failed to create CallbackHandler: {e}")
            return None

    def get_client(self):
        """
        获取 Langfuse 客户端实例

        Returns:
            Langfuse 客户端，如果不可用则返回 None
        """
        return self._client if self._enabled else None

    async def health_check(self) -> dict:
        """
        检查 Langfuse 服务健康状态

        Returns:
            {
                "status": "healthy" | "unhealthy" | "disabled",
                "url": str,
                "message": str
            }
        """
        if not self._enabled:
            return {
                "status": "disabled",
                "url": self._base_url,
                "message": "Langfuse is not configured or unavailable"
            }

        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/api/public/health")
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "url": self._base_url,
                        "message": "Langfuse is operational"
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "url": self._base_url,
                        "message": f"Health check returned status {response.status_code}"
                    }
        except Exception as e:
            return {
                "status": "unhealthy",
                "url": self._base_url,
                "message": f"Health check failed: {str(e)}"
            }

    def flush(self):
        """确保所有 trace 数据发送完成（用于 shutdown）"""
        if self._client:
            try:
                self._client.flush()
            except Exception as e:
                logger.warning(f"Failed to flush Langfuse traces: {e}")

    async def get_usage_stats(
        self,
        granularity: Literal["day", "week", "month"] = "day",
        days: int = 30,
    ) -> dict[str, Any]:
        """
        从 Langfuse 查询 token 用量统计

        Args:
            granularity: 时间聚合粒度 (day/week/month)
            days: 查询时间范围（天数）

        Returns:
            {
                "granularity": str,
                "period_days": int,
                "total_tokens": int,
                "input_tokens": int,
                "output_tokens": int,
                "total_cost_usd": float,
                "total_calls": int,
                "by_time": [...],
                "by_model": [...],
                "by_user": [...]
            }
        """
        if not self._enabled or not self._client:
            return {
                "granularity": granularity,
                "period_days": days,
                "total_tokens": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_cost_usd": 0.0,
                "total_calls": 0,
                "by_time": [],
                "by_model": [],
                "by_user": [],
                "error": "Langfuse is not enabled",
            }

        try:
            start_time = datetime.now(timezone.utc) - timedelta(days=days)

            # Fetch both GENERATION and TOOL observations
            # TOOL type is created by LiteLLM OTEL callback (named "raw_gen_ai_request")
            # and contains the bulk of token usage data
            all_observations: list[Any] = []
            seen_ids: set[str] = set()

            for obs_type in ["GENERATION", "TOOL"]:
                page = 1
                while True:
                    result = self._client.api.observations.get_many(
                        type=obs_type,
                        from_start_time=start_time,
                        limit=100,
                        page=page,
                    )

                    for obs in result.data:
                        # Deduplicate by observation ID
                        if obs.id not in seen_ids:
                            seen_ids.add(obs.id)
                            all_observations.append(obs)

                    # Check if there are more pages
                    if hasattr(result, "meta") and hasattr(result.meta, "total_pages"):
                        if page >= result.meta.total_pages:
                            break
                    elif len(result.data) < 100:
                        # No more results
                        break
                    page += 1

                    # Safety limit per type
                    if page > 100:
                        logger.warning(f"Reached max page limit when fetching {obs_type} observations")
                        break

            # Pre-fetch trace user mappings to avoid N+1 queries
            # Collect unique trace_ids first
            trace_ids = set()
            for obs in all_observations:
                if hasattr(obs, "trace_id") and obs.trace_id:
                    trace_ids.add(obs.trace_id)

            # Fetch traces concurrently for better performance
            trace_user_map: dict[str, str] = {}
            client = self._client  # Capture for closure

            def fetch_trace_user(trace_id: str) -> tuple[str, str | None]:
                try:
                    if client is None:
                        return (trace_id, None)
                    trace = client.api.trace.get(trace_id)
                    if hasattr(trace, "user_id") and trace.user_id:
                        return (trace_id, trace.user_id)
                except Exception:
                    pass
                return (trace_id, None)

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(fetch_trace_user, tid) for tid in trace_ids]
                for future in as_completed(futures):
                    trace_id, user_id = future.result()
                    if user_id:
                        trace_user_map[trace_id] = user_id

            # Aggregate statistics
            total_input = 0
            total_output = 0
            total_cost = 0.0
            total_calls = len(all_observations)

            # Time-based aggregation
            time_stats: dict[str, dict[str, Any]] = defaultdict(
                lambda: {"tokens": 0, "cost": 0.0, "calls": 0}
            )
            # Model-based aggregation
            model_stats: dict[str, dict[str, Any]] = defaultdict(
                lambda: {"tokens": 0, "cost": 0.0, "calls": 0}
            )
            # User-based aggregation
            user_stats: dict[str, dict[str, Any]] = defaultdict(
                lambda: {"tokens": 0, "cost": 0.0, "calls": 0}
            )

            for obs in all_observations:
                # Extract usage data
                input_tokens = 0
                output_tokens = 0
                cost = 0.0

                # Use usage_details (Dict[str, int]) instead of deprecated usage field
                if hasattr(obs, "usage_details") and obs.usage_details:
                    usage_details = obs.usage_details
                    input_tokens = usage_details.get("input", 0) or 0
                    output_tokens = usage_details.get("output", 0) or 0

                # Use cost_details (Dict[str, float]) instead of deprecated calculated_total_cost
                if hasattr(obs, "cost_details") and obs.cost_details:
                    cost_details = obs.cost_details
                    cost = cost_details.get("total", 0.0) or 0.0

                total_input += input_tokens
                total_output += output_tokens
                total_cost += cost
                tokens = input_tokens + output_tokens

                # Time aggregation
                if hasattr(obs, "start_time") and obs.start_time:
                    time_key = self._get_time_key(obs.start_time, granularity)
                    time_stats[time_key]["tokens"] += tokens
                    time_stats[time_key]["cost"] += cost
                    time_stats[time_key]["calls"] += 1

                # Model aggregation
                model_name = getattr(obs, "model", "unknown") or "unknown"
                model_stats[model_name]["tokens"] += tokens
                model_stats[model_name]["cost"] += cost
                model_stats[model_name]["calls"] += 1

                # User aggregation - use pre-fetched trace data
                user_id = "anonymous"
                if hasattr(obs, "trace_id") and obs.trace_id:
                    user_id = trace_user_map.get(obs.trace_id, "anonymous")
                user_stats[user_id]["tokens"] += tokens
                user_stats[user_id]["cost"] += cost
                user_stats[user_id]["calls"] += 1

            # Format results
            by_time = [
                {"date": k, "tokens": v["tokens"], "cost": round(v["cost"], 4), "calls": v["calls"]}
                for k, v in sorted(time_stats.items(), reverse=True)
            ]

            by_model = [
                {"model": k, "tokens": v["tokens"], "cost": round(v["cost"], 4), "calls": v["calls"]}
                for k, v in sorted(model_stats.items(), key=lambda x: x[1]["tokens"], reverse=True)
            ]

            # Batch query usernames from database
            from backend.auth.database import get_users_by_ids

            user_ids = [k for k in user_stats.keys() if k != "anonymous"]
            usernames = await get_users_by_ids(user_ids)

            by_user = [
                {
                    "user_id": k,
                    "username": usernames.get(k, k),  # Use username if found, otherwise user_id
                    "tokens": v["tokens"],
                    "cost": round(v["cost"], 4),
                    "calls": v["calls"]
                }
                for k, v in sorted(user_stats.items(), key=lambda x: x[1]["tokens"], reverse=True)
            ]

            return {
                "granularity": granularity,
                "period_days": days,
                "total_tokens": total_input + total_output,
                "input_tokens": total_input,
                "output_tokens": total_output,
                "total_cost_usd": round(total_cost, 4),
                "total_calls": total_calls,
                "by_time": by_time,
                "by_model": by_model,
                "by_user": by_user,
            }

        except Exception as e:
            logger.exception(f"Failed to get usage stats from Langfuse: {e}")
            return {
                "granularity": granularity,
                "period_days": days,
                "total_tokens": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_cost_usd": 0.0,
                "total_calls": 0,
                "by_time": [],
                "by_model": [],
                "by_user": [],
                "error": str(e),
            }

    def _get_time_key(self, dt: datetime, granularity: Literal["day", "week", "month"]) -> str:
        """Get time key based on granularity for aggregation."""
        if granularity == "day":
            return dt.strftime("%Y-%m-%d")
        elif granularity == "week":
            return dt.strftime("%Y-W%W")
        else:  # month
            return dt.strftime("%Y-%m")


# 全局单例
_langfuse_service: Optional[LangfuseService] = None


def get_langfuse_service() -> LangfuseService:
    """获取 LangfuseService 单例"""
    global _langfuse_service
    if _langfuse_service is None:
        _langfuse_service = LangfuseService()
    return _langfuse_service


def reset_langfuse_service():
    """重置 LangfuseService 单例（用于测试）"""
    global _langfuse_service
    if _langfuse_service:
        _langfuse_service.flush()
    _langfuse_service = None


def get_langfuse_config() -> dict:
    """获取 Langfuse 配置信息（用于前端显示）

    Returns:
        {
            "enabled": bool,
            "url": str,  # Langfuse UI URL for admin access
        }
    """
    service = get_langfuse_service()
    return {
        "enabled": service.enabled,
        "url": service.base_url,
    }
