#!/usr/bin/env python3
"""
Langfuse Experiment Runner - 通过 Langfuse Dataset 评估 SunnyAgent

使用方法:
    1. 在 Langfuse 中创建 Dataset 并添加测试用例
    2. 运行此脚本: python scripts/evaluation/run_experiment.py --dataset <dataset_name>
    3. 在 Langfuse 界面查看评估结果

环境变量:
    - LANGFUSE_PUBLIC_KEY: Langfuse 公钥
    - LANGFUSE_SECRET_KEY: Langfuse 私钥
    - LANGFUSE_HOST: Langfuse 服务地址 (默认: http://localhost:3001)
    - SUNNYAGENT_API_URL: SunnyAgent API 地址 (默认: http://localhost:8008)
    - SUNNYAGENT_USERNAME: SunnyAgent 用户名
    - SUNNYAGENT_PASSWORD: SunnyAgent 密码
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any

import httpx
from langfuse import Langfuse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SunnyAgentClient:
    """SunnyAgent API Client for evaluation."""

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._token: str | None = None

    async def login(self) -> None:
        """Authenticate with SunnyAgent."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/login",
                json={"username": self.username, "password": self.password},
            )
            response.raise_for_status()
            # Token is set via cookie
            self._token = response.cookies.get("access_token")
            logger.info(f"Logged in as {self.username}")

    async def chat(self, message: str, thread_id: str | None = None) -> dict[str, Any]:
        """Send a chat message and collect the full response.

        Args:
            message: User message
            thread_id: Optional thread ID for conversation context

        Returns:
            {
                "thread_id": str,
                "response": str,  # Full response text
                "tool_calls": list,  # Tool calls made
                "duration_ms": int,  # Total duration
            }
        """
        if not self._token:
            await self.login()

        # Create conversation if no thread_id
        if not thread_id:
            async with httpx.AsyncClient(cookies={"access_token": self._token}) as client:
                response = await client.post(f"{self.base_url}/api/conversations")
                response.raise_for_status()
                conv = response.json()
                thread_id = conv["thread_id"]

        # Send chat message via SSE
        response_text = ""
        tool_calls = []
        start_time = datetime.now()

        async with httpx.AsyncClient(
            cookies={"access_token": self._token},
            timeout=httpx.Timeout(300.0),  # 5 minutes timeout
        ) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={"thread_id": thread_id, "message": message},
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    try:
                        data = json.loads(line[6:])  # Remove "data: " prefix
                        event_type = data.get("event")

                        if event_type == "text_delta":
                            text = json.loads(data.get("data", "{}")).get("text", "")
                            response_text += text
                        elif event_type == "tool_call_result":
                            tool_data = json.loads(data.get("data", "{}"))
                            tool_calls.append(tool_data)
                        elif event_type == "done":
                            break
                    except json.JSONDecodeError:
                        continue

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return {
            "thread_id": thread_id,
            "response": response_text.strip(),
            "tool_calls": tool_calls,
            "duration_ms": duration_ms,
        }


async def run_experiment(
    dataset_name: str,
    experiment_name: str | None = None,
    evaluators: list[str] | None = None,
) -> None:
    """Run evaluation experiment using Langfuse dataset.

    Args:
        dataset_name: Name of the Langfuse dataset
        experiment_name: Optional experiment name (defaults to timestamp)
        evaluators: List of evaluator names to run
    """
    # Initialize Langfuse client
    langfuse = Langfuse()

    # Get dataset
    dataset = langfuse.get_dataset(dataset_name)
    if not dataset:
        logger.error(f"Dataset '{dataset_name}' not found")
        sys.exit(1)

    logger.info(f"Running experiment on dataset: {dataset_name}")
    logger.info(f"Dataset has {len(dataset.items)} items")

    # Initialize SunnyAgent client
    api_url = os.getenv("SUNNYAGENT_API_URL", "http://localhost:8008")
    username = os.getenv("SUNNYAGENT_USERNAME", "admin")
    password = os.getenv("SUNNYAGENT_PASSWORD")

    if not password:
        logger.error("SUNNYAGENT_PASSWORD environment variable required")
        sys.exit(1)

    client = SunnyAgentClient(api_url, username, password)
    await client.login()

    # Generate experiment name
    if not experiment_name:
        experiment_name = f"eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    logger.info(f"Experiment name: {experiment_name}")

    # Process each dataset item
    results = []
    for i, item in enumerate(dataset.items):
        logger.info(f"Processing item {i + 1}/{len(dataset.items)}: {item.id}")

        try:
            # Extract input from dataset item
            input_message = item.input.get("message", "") if isinstance(item.input, dict) else str(item.input)

            # Call SunnyAgent
            result = await client.chat(input_message)

            # Create run in Langfuse
            trace = langfuse.trace(
                name=f"eval-{item.id}",
                input={"message": input_message},
                output={"response": result["response"]},
                metadata={
                    "experiment": experiment_name,
                    "dataset": dataset_name,
                    "item_id": item.id,
                    "duration_ms": result["duration_ms"],
                    "tool_calls_count": len(result["tool_calls"]),
                },
            )

            # Link trace to dataset item
            item.link(trace, experiment_name)

            # Run evaluators if configured
            if evaluators:
                from evaluators import run_evaluators

                eval_results = await run_evaluators(
                    evaluators=evaluators,
                    input_message=input_message,
                    output_response=result["response"],
                    expected_output=item.expected_output,
                )

                for eval_name, score in eval_results.items():
                    trace.score(name=eval_name, value=score)

            results.append({
                "item_id": item.id,
                "status": "success",
                "duration_ms": result["duration_ms"],
            })

            logger.info(f"  Completed in {result['duration_ms']}ms")

        except Exception as e:
            logger.error(f"  Failed: {e}")
            results.append({
                "item_id": item.id,
                "status": "error",
                "error": str(e),
            })

    # Flush Langfuse data
    langfuse.flush()

    # Print summary
    successful = sum(1 for r in results if r["status"] == "success")
    failed = len(results) - successful
    avg_duration = sum(r.get("duration_ms", 0) for r in results if r["status"] == "success") / max(successful, 1)

    logger.info("\n" + "=" * 50)
    logger.info("EXPERIMENT SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Dataset: {dataset_name}")
    logger.info(f"Experiment: {experiment_name}")
    logger.info(f"Total items: {len(results)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Avg duration: {avg_duration:.0f}ms")
    logger.info("=" * 50)
    logger.info(f"\nView results in Langfuse: {os.getenv('LANGFUSE_HOST', 'http://localhost:3001')}")


def main():
    parser = argparse.ArgumentParser(description="Run SunnyAgent evaluation experiment")
    parser.add_argument(
        "--dataset",
        "-d",
        required=True,
        help="Langfuse dataset name",
    )
    parser.add_argument(
        "--experiment",
        "-e",
        help="Experiment name (defaults to timestamp)",
    )
    parser.add_argument(
        "--evaluators",
        nargs="+",
        choices=["relevance", "correctness", "completeness"],
        help="Evaluators to run",
    )

    args = parser.parse_args()

    asyncio.run(
        run_experiment(
            dataset_name=args.dataset,
            experiment_name=args.experiment,
            evaluators=args.evaluators,
        )
    )


if __name__ == "__main__":
    main()
