"""
LLM-as-a-Judge Evaluators for SunnyAgent

支持的评估指标:
- relevance: 回复与问题的相关性 (0-1)
- correctness: 回复的正确性 (0-1)
- completeness: 回复的完整性 (0-1)

使用方法:
    from evaluators import run_evaluators

    results = await run_evaluators(
        evaluators=["relevance", "correctness"],
        input_message="用户问题",
        output_response="Agent 回复",
        expected_output={"answer": 42},  # 可选
    )
"""

import json
import logging
import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Evaluator prompts
RELEVANCE_PROMPT = """你是一个评估助手。请评估以下 AI 回复与用户问题的相关性。

用户问题:
{input_message}

AI 回复:
{output_response}

评分标准:
- 1.0: 完全相关，直接回答了用户的问题
- 0.8: 大部分相关，回答了主要问题
- 0.6: 部分相关，涉及问题但有偏题
- 0.4: 较少相关，大部分内容不相关
- 0.2: 几乎不相关
- 0.0: 完全不相关

请只返回一个 0 到 1 之间的数字（保留1位小数），不要有任何其他文字。"""

CORRECTNESS_PROMPT = """你是一个评估助手。请评估以下 AI 回复的正确性。

用户问题:
{input_message}

AI 回复:
{output_response}

{expected_context}

评分标准:
- 1.0: 完全正确，没有事实错误
- 0.8: 基本正确，有细微偏差
- 0.6: 部分正确，有一些错误
- 0.4: 错误较多
- 0.2: 大部分错误
- 0.0: 完全错误

请只返回一个 0 到 1 之间的数字（保留1位小数），不要有任何其他文字。"""

COMPLETENESS_PROMPT = """你是一个评估助手。请评估以下 AI 回复的完整性。

用户问题:
{input_message}

AI 回复:
{output_response}

评分标准:
- 1.0: 非常完整，涵盖了所有重要方面
- 0.8: 比较完整，涵盖了主要内容
- 0.6: 基本完整，有一些遗漏
- 0.4: 不够完整，遗漏较多
- 0.2: 很不完整
- 0.0: 几乎没有有效内容

请只返回一个 0 到 1 之间的数字（保留1位小数），不要有任何其他文字。"""


def _get_llm():
    """Get LLM for evaluation (uses OpenAI by default)."""
    # Try to use the same provider as SunnyAgent
    provider = os.getenv("LLM_PROVIDER", "openai")

    if provider == "openai":
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model="claude-3-haiku-20240307",
            temperature=0,
        )
    elif provider in ("deepseek", "deepseek_gateway"):
        # Use OpenAI-compatible client for DeepSeek
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_GATEWAY_API_KEY")
        base_url = (
            "https://api.deepseek.com/v1"
            if provider == "deepseek"
            else "https://api.volceapi.com/v1"
        )
        return ChatOpenAI(
            model="deepseek-chat",
            api_key=api_key,
            base_url=base_url,
            temperature=0,
        )
    else:
        # Default to OpenAI
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)


async def evaluate_relevance(input_message: str, output_response: str) -> float:
    """Evaluate relevance of response to input (0-1)."""
    llm = _get_llm()

    prompt = RELEVANCE_PROMPT.format(
        input_message=input_message,
        output_response=output_response,
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        score = float(response.content.strip())
        return max(0.0, min(1.0, score))
    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to parse relevance score: {e}")
        return 0.5


async def evaluate_correctness(
    input_message: str,
    output_response: str,
    expected_output: dict[str, Any] | None = None,
) -> float:
    """Evaluate correctness of response (0-1)."""
    llm = _get_llm()

    # Build expected context if available
    expected_context = ""
    if expected_output:
        if "answer" in expected_output:
            expected_context = f"预期答案: {expected_output['answer']}"
        elif "contains" in expected_output:
            expected_context = f"回复应包含: {', '.join(expected_output['contains'])}"

    prompt = CORRECTNESS_PROMPT.format(
        input_message=input_message,
        output_response=output_response,
        expected_context=expected_context,
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        score = float(response.content.strip())
        return max(0.0, min(1.0, score))
    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to parse correctness score: {e}")
        return 0.5


async def evaluate_completeness(input_message: str, output_response: str) -> float:
    """Evaluate completeness of response (0-1)."""
    llm = _get_llm()

    prompt = COMPLETENESS_PROMPT.format(
        input_message=input_message,
        output_response=output_response,
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        score = float(response.content.strip())
        return max(0.0, min(1.0, score))
    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to parse completeness score: {e}")
        return 0.5


async def run_evaluators(
    evaluators: list[str],
    input_message: str,
    output_response: str,
    expected_output: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Run specified evaluators and return scores.

    Args:
        evaluators: List of evaluator names ("relevance", "correctness", "completeness")
        input_message: Original user message
        output_response: Agent's response
        expected_output: Optional expected output for correctness evaluation

    Returns:
        Dict mapping evaluator name to score (0-1)
    """
    results = {}

    for evaluator in evaluators:
        try:
            if evaluator == "relevance":
                score = await evaluate_relevance(input_message, output_response)
            elif evaluator == "correctness":
                score = await evaluate_correctness(input_message, output_response, expected_output)
            elif evaluator == "completeness":
                score = await evaluate_completeness(input_message, output_response)
            else:
                logger.warning(f"Unknown evaluator: {evaluator}")
                continue

            results[evaluator] = score
            logger.info(f"  {evaluator}: {score:.2f}")

        except Exception as e:
            logger.error(f"Evaluator {evaluator} failed: {e}")
            results[evaluator] = 0.0

    return results


# Langfuse evaluator configurations for UI-based evaluation
LANGFUSE_EVALUATOR_CONFIGS = {
    "relevance": {
        "name": "relevance",
        "description": "评估回复与问题的相关性",
        "data_type": "NUMERIC",
        "min_value": 0,
        "max_value": 1,
    },
    "correctness": {
        "name": "correctness",
        "description": "评估回复的正确性",
        "data_type": "NUMERIC",
        "min_value": 0,
        "max_value": 1,
    },
    "completeness": {
        "name": "completeness",
        "description": "评估回复的完整性",
        "data_type": "NUMERIC",
        "min_value": 0,
        "max_value": 1,
    },
}
