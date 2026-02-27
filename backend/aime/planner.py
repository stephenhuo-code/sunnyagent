"""AIME Planner - orchestrates intent analysis and action execution.

The Planner is the core decision-making component of AIME:
1. Analyzes user intent via IntentAnalyzer
2. Executes appropriate action based on IntentResult
3. Yields SSE events for frontend display

Action handling:
- direct_reply: Generate response directly via LLM streaming
- delegate: Route to specialist agent (US2)
- plan: Decompose into subtasks (US4)
- clarify: Ask clarification questions
"""

import asyncio
import json
import logging
import time
import traceback
from typing import Any, AsyncGenerator
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.aime.actor_factory import ActorFactory
from backend.aime.context import AgentContext
from backend.aime.context_manager import ContextManager
from backend.aime.intent import IntentAnalyzer, IntentResult
from backend.aime.models import Actor, SubtaskSpec
from backend.aime.progress_manager import ProgressManager
from backend.llm import get_model
from backend.services.langfuse_service import get_langfuse_service

logger = logging.getLogger(__name__)


# Direct reply system prompt for simple queries
_DIRECT_REPLY_PROMPT = """\
你是一个有帮助的 AI 助手。请直接、简洁地回复用户消息。

**重要：你必须始终用中文回复用户。**

指南：
- 友好且乐于助人
- 保持回复聚焦和相关
- 适当使用 markdown 格式
- 数学问题请展示计算过程
- 事实问题请提供准确信息
"""

# Task failure marker - agents should use this prefix when they cannot complete a task
TASK_FAILED_MARKER = "[TASK_FAILED]"

# Task instruction template that instructs agents to declare failure explicitly
TASK_INSTRUCTION_TEMPLATE = """{description}

## 重要指令
如果你无法完成此任务（例如：没有数据访问权限、找不到相关信息、缺少必要资源），
请在回复开头明确声明：

[TASK_FAILED] 原因: <简要说明无法完成的原因>

然后可以提供替代建议。

如果你能够完成任务，直接提供结果，无需任何前缀。
"""


def _format_sse(event: str, data: dict, event_id: int) -> dict[str, Any]:
    """Format SSE event for streaming.

    Args:
        event: Event type name
        data: Event payload
        event_id: Sequential event ID

    Returns:
        SSE event dict compatible with stream_handler.py format
    """
    return {
        "event": event,
        "data": json.dumps(data, ensure_ascii=False),
        "id": str(event_id),
    }


class AIMEPlanner:
    """AIME Planner - orchestrates intent analysis and task execution.

    Attributes:
        intent_analyzer: Intent analyzer for classifying user messages
        actor_factory: Factory for selecting and instantiating actors
        progress_manager: Manager for task progress tracking
        model: LLM model for direct responses
    """

    def __init__(
        self,
        intent_analyzer: IntentAnalyzer | None = None,
        actor_factory: ActorFactory | None = None,
        progress_manager: ProgressManager | None = None,
        context_manager: ContextManager | None = None,
    ):
        """Initialize the AIME Planner.

        Args:
            intent_analyzer: Optional custom intent analyzer
            actor_factory: Optional custom actor factory (user_id set per-request)
            progress_manager: Optional custom progress manager
            context_manager: Optional custom context manager
        """
        self.intent_analyzer = intent_analyzer or IntentAnalyzer()
        self._actor_factory_base = actor_factory  # Store base factory if provided
        # ActorFactory is created per-request with user_id in process()
        # Initialize with a default factory (no user filtering)
        self.actor_factory: ActorFactory = actor_factory or ActorFactory()
        self.progress_manager = progress_manager or ProgressManager()
        self.context_manager = context_manager or ContextManager()
        self._model = get_model("supervisor")
        logger.info("AIMEPlanner initialized with ContextManager")

    async def process(
        self,
        message: str,
        thread_id: str,
        context: AgentContext | dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Process user message and yield SSE events.

        Main entry point for AIME processing. Analyzes intent and
        executes the appropriate action handler.

        Args:
            message: User message
            thread_id: Conversation thread ID
            context: AgentContext or legacy dict (for backwards compatibility)

        Yields:
            SSE event dicts for frontend streaming
        """
        event_id = 0

        # Extract user_id and store context reference for later use
        if isinstance(context, AgentContext):
            self._current_user_id = context.session.user_id
            self._current_context = context  # Store for injection at execution time
        elif isinstance(context, dict):
            self._current_user_id = context.get("user_id")
            self._current_context = None  # No AgentContext available
        else:
            self._current_user_id = None
            self._current_context = None

        # Create ActorFactory with current user_id for plugin filtering
        if self._actor_factory_base:
            # If a base factory was provided, create new one with user_id
            self.actor_factory = ActorFactory(user_id=self._current_user_id)
        else:
            self.actor_factory = ActorFactory(user_id=self._current_user_id)

        # Log entry point
        logger.info(
            f"[process] Starting - thread_id={thread_id}, "
            f"message='{message[:50]}...'"
        )

        # Initialize Langfuse tracing context
        langfuse_service = get_langfuse_service()
        langfuse_client = langfuse_service.get_client() if langfuse_service.enabled else None
        trace_context = None

        # Start Langfuse trace for this request
        if langfuse_client:
            try:
                # Fallback: ensure user_id is not None for Langfuse
                effective_user_id = self._current_user_id or f"anonymous-{thread_id[:8]}"

                # Create trace (SDK v3: as_type="trace" works at runtime but pyright type stubs don't include it)
                trace_context = langfuse_client.start_as_current_observation(
                    as_type="trace",  # type: ignore[arg-type]
                    name="aime-planner",
                )
                trace_context.__enter__()

                # Use update_current_trace to set user_id and session_id (SDK v3 pattern)
                langfuse_client.update_current_trace(
                    user_id=effective_user_id,
                    session_id=thread_id,
                    input={"message": message[:500], "thread_id": thread_id},
                )
            except Exception as e:
                logger.warning(f"Failed to start Langfuse trace: {e}")

        try:
            # Analyze user intent - pass AgentContext directly
            # IntentAnalyzer will extract simplified context (no file_id, project_id)
            intent = await self.intent_analyzer.analyze(message, context)
            logger.info(
                f"[process] Intent analyzed - action={intent.action}, "
                f"confidence={intent.confidence}, "
                f"capabilities={intent.capabilities}"
            )

            # Route to appropriate action handler
            if intent.action == "direct_reply":
                async for event in self._handle_direct_reply(
                    message, thread_id, intent, event_id
                ):
                    event_id += 1
                    yield event

            elif intent.action == "clarify":
                async for event in self._handle_clarify(intent, event_id):
                    event_id += 1
                    yield event

            elif intent.action == "delegate":
                # US2: Delegate to specialist agent
                async for event in self._handle_delegate(
                    message, thread_id, intent, event_id
                ):
                    event_id += 1
                    yield event

            elif intent.action == "plan":
                # US4: Complex task decomposition
                async for event in self._handle_plan(
                    message, thread_id, intent, event_id
                ):
                    event_id += 1
                    yield event

            elif intent.action == "command":
                # User invoked a /command
                async for event in self._handle_command(
                    message, thread_id, intent, event_id
                ):
                    event_id += 1
                    yield event

            else:
                # Fallback to direct reply for unknown actions
                logger.warning(f"Unknown action: {intent.action}, falling back to direct_reply")
                async for event in self._handle_direct_reply(
                    message, thread_id, intent, event_id
                ):
                    event_id += 1
                    yield event

        except asyncio.TimeoutError as e:
            # Handle timeout specifically - record partial trace
            logger.warning(f"Timeout in AIMEPlanner.process: {e}")
            yield _format_sse("error", {"message": "请求超时，请稍后重试"}, event_id)
            event_id += 1

            # Record timeout in Langfuse trace with partial status
            if trace_context and langfuse_client:
                try:
                    langfuse_client.update_current_trace(
                        output={"error": "timeout", "partial": True},
                    )
                except Exception:
                    pass

        except Exception as e:
            logger.exception(f"Error in AIMEPlanner.process: {e}")
            yield _format_sse("error", {"message": str(e)}, event_id)
            event_id += 1

            # Record error in Langfuse trace
            if trace_context and langfuse_client:
                try:
                    langfuse_client.update_current_trace(
                        output={"error": str(e)},
                    )
                except Exception:
                    pass

        finally:
            # Always close Langfuse trace (ensures partial traces are recorded)
            if trace_context:
                try:
                    trace_context.__exit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Failed to close Langfuse trace: {e}")

        # Always emit done event
        yield _format_sse("done", {}, event_id)

    async def _handle_direct_reply(
        self,
        message: str,
        thread_id: str,
        intent: IntentResult,
        start_event_id: int,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Handle direct_reply action - generate response via LLM.

        Streams text_delta events as the LLM generates response.

        Args:
            message: User message
            thread_id: Thread ID
            intent: Analyzed intent
            start_event_id: Starting event ID

        Yields:
            SSE events (text_delta)
        """
        logger.info(f"[_handle_direct_reply] Starting direct response generation")
        event_id = start_event_id

        # Build messages list with context as SystemMessage (not injected into user message)
        llm_messages: list[SystemMessage | HumanMessage] = [SystemMessage(content=_DIRECT_REPLY_PROMPT)]

        # Add context as a separate SystemMessage to avoid polluting user message
        if self._current_context:
            context_prompt = self._current_context.build_context_prompt()
            if context_prompt:
                llm_messages.append(SystemMessage(content=f"当前上下文:\n{context_prompt}"))
                logger.info("[_handle_direct_reply] Injected file context as SystemMessage")

        # User message stays clean (no context injection)
        llm_messages.append(HumanMessage(content=message))

        # Create Langfuse span for LLM generation
        # NOTE: Using start_generation() instead of start_as_current_observation() to avoid
        # context loss issues with async generators and type checking warnings.
        langfuse_service = get_langfuse_service()
        langfuse_client = langfuse_service.get_client() if langfuse_service.enabled else None
        span = None  # Direct span object reference

        if langfuse_client:
            try:
                span = langfuse_client.start_generation(
                    name="direct-reply-llm",
                    model=getattr(self._model, "model", None) or getattr(self._model, "model_name", "unknown"),
                    input={"message": message[:500]},
                )
            except Exception:
                pass

        output_text = ""
        final_usage = None  # Collect final token usage (only last chunk has it)
        try:
            # Stream response from LLM
            async for chunk in self._model.astream(llm_messages):
                if hasattr(chunk, "content") and chunk.content:
                    # Handle both string and list content types
                    content = chunk.content
                    if isinstance(content, str):
                        text_chunk = content
                    elif isinstance(content, list):
                        # For list content (multimodal), extract text parts
                        text_chunk = "".join(
                            str(item) if isinstance(item, str) else item.get("text", "")
                            for item in content
                            if isinstance(item, (str, dict))
                        )
                    else:
                        text_chunk = str(content)

                    output_text += text_chunk
                    yield _format_sse(
                        "text_delta",
                        {"text": text_chunk},
                        event_id,
                    )
                    event_id += 1

                # Extract token usage from chunk if available (last chunk contains usage)
                if hasattr(chunk, "response_metadata"):
                    metadata = chunk.response_metadata
                    if "token_usage" in metadata:
                        final_usage = metadata["token_usage"]

        except Exception as e:
            logger.exception(f"Error streaming direct reply: {e}")
            yield _format_sse(
                "text_delta",
                {"text": f"抱歉，生成回复时出错：{str(e)}"},
                event_id,
            )
            if span:
                try:
                    span.update(output={"error": str(e)})
                except Exception:
                    pass
        finally:
            if span:
                try:
                    output_data: dict[str, Any] = {"text": output_text[:500]}
                    # Apply final token usage collected from last chunk
                    if final_usage:
                        span.update(
                            output=output_data,
                            usage={
                                "input": final_usage.get("prompt_tokens", 0),
                                "output": final_usage.get("completion_tokens", 0),
                                "total": final_usage.get("total_tokens", 0),
                            }
                        )
                    else:
                        span.update(output=output_data)
                    span.end()
                except Exception:
                    pass

        # Persist direct reply messages to checkpoint for history retrieval
        # This ensures "hello" type messages are saved even though they bypass LangGraph
        if output_text:
            try:
                from backend.checkpointer_store import get_history_graph
                from langchain_core.runnables.config import RunnableConfig
                history_graph = get_history_graph()
                if history_graph:
                    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
                    await history_graph.aupdate_state(
                        config,
                        {"messages": [HumanMessage(content=message), AIMessage(content=output_text)]}
                    )
                    logger.info(f"[_handle_direct_reply] Persisted messages to checkpoint")
            except Exception as e:
                logger.warning(f"[_handle_direct_reply] Failed to persist messages: {e}")

    async def _handle_clarify(
        self,
        intent: IntentResult,
        start_event_id: int,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Handle clarify action - ask for clarification.

        Args:
            intent: Intent with clarify_questions
            start_event_id: Starting event ID

        Yields:
            SSE events with clarification questions
        """
        event_id = start_event_id
        questions = intent.clarify_questions or ["Could you please provide more details?"]

        response = "我需要一些澄清才能更好地帮助你：\n\n"
        for i, q in enumerate(questions, 1):
            response += f"{i}. {q}\n"

        yield _format_sse("text_delta", {"text": response}, event_id)

    async def _handle_delegate(
        self,
        message: str,
        thread_id: str,
        intent: IntentResult,
        start_event_id: int,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Handle delegate action - route to specialist agent.

        Creates a single subtask and executes it via the selected actor.

        Args:
            message: User message
            thread_id: Thread ID
            intent: Analyzed intent with capabilities/explicit_agent
            start_event_id: Starting event ID

        Yields:
            SSE events (thinking, task_spawned, text_delta, task_completed)
        """
        logger.info(
            f"[_handle_delegate] Starting - explicit_agent={intent.explicit_agent}, "
            f"capabilities={intent.capabilities}"
        )
        event_id = start_event_id

        # Create subtask spec from intent
        spec = SubtaskSpec(
            id=str(uuid4()),
            description=message,
            explicit_agent=intent.explicit_agent,
            capabilities=intent.capabilities,
        )

        try:
            # Select actor using ActorFactory (async for plugin filtering)
            actor = await self.actor_factory.select_actor(spec)
            logger.info(f"[_handle_delegate] Actor selected: {actor.name}")

            # Emit thinking event (routing decision)
            yield _format_sse(
                "thinking",
                {
                    "content": f"Routing to {actor.name}: {message[:100]}...",
                    "type": "routing",
                },
                event_id,
            )
            event_id += 1

            # Add task to progress manager
            self.progress_manager.add_task(spec)

            # Emit task_spawned with pending status (task created but not yet started)
            yield _format_sse(
                "task_spawned",
                {
                    "task_id": spec.id,
                    "subagent_type": actor.name,
                    "description": message[:200],
                    "status": "pending",
                },
                event_id,
            )
            event_id += 1

            # Emit task_started when execution begins
            yield _format_sse(
                "task_started",
                {"task_id": spec.id},
                event_id,
            )
            event_id += 1

            # Start task in progress manager
            self.progress_manager.start_task(spec.id, actor.name)

            # Get context prompt to pass as system_context (not injected into user message)
            context_prompt = None
            if self._current_context:
                context_prompt = self._current_context.build_context_prompt()
                if context_prompt:
                    logger.info(f"[_handle_delegate] Will pass context as system_context")

            # Execute actor with task_id for tool call association
            # Pass context as system_context to avoid polluting user message history
            start_time = time.time()
            result_text = ""  # Collect task output for final summary
            async for event in self._execute_actor(
                actor, message, thread_id, event_id,
                task_id=spec.id,
                user_id=self._current_user_id,
                system_context=context_prompt,
            ):
                event_id += 1
                # Ensure tool_call events are associated with this task
                # (Same transformation as _handle_plan to maintain consistent display)
                event_type = event.get("event")
                if event_type in ("tool_call_start", "tool_call_result"):
                    data = json.loads(event.get("data", "{}"))
                    # Force task_id to be the delegate task's ID
                    data["task_id"] = spec.id
                    yield _format_sse(str(event_type), data, event_id)
                elif event.get("event") == "text_delta":
                    # Convert text_delta to task_output (same as plan mode)
                    data = json.loads(event.get("data", "{}"))
                    text_chunk = data.get("text", "")
                    result_text += text_chunk  # Collect for final summary
                    yield _format_sse(
                        "task_output",
                        {"task_id": spec.id, "text": text_chunk},
                        event_id,
                    )
                else:
                    yield event

            # Complete task
            duration_ms = int((time.time() - start_time) * 1000)
            self.progress_manager.complete_task(spec.id, "completed")
            logger.info(
                f"[_handle_delegate] Completed - task_id={spec.id[:8]}, "
                f"duration_ms={duration_ms}"
            )
            yield _format_sse(
                "task_completed",
                {
                    "task_id": spec.id,
                    "status": "success",
                    "duration_ms": duration_ms,
                },
                event_id,
            )
            event_id += 1

            # Output collected result to result area (text_delta)
            # This ensures the final answer appears outside the task node
            if result_text:
                yield _format_sse(
                    "text_delta",
                    {"text": f"\n\n{result_text}"},
                    event_id,
                )

            # Persist delegate metadata to checkpoint for history retrieval
            try:
                from backend.checkpointer_store import get_history_graph
                from langchain_core.runnables.config import RunnableConfig
                history_graph = get_history_graph()
                if history_graph:
                    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
                    # Build thinking_steps from the routing event
                    thinking_steps = [
                        {
                            "type": "routing",
                            "content": f"Routing to {actor.name}: {message[:100]}...",
                            "timestamp": int(time.time() * 1000),
                        }
                    ]
                    # Build spawned_tasks
                    spawned_tasks = [
                        {
                            "task_id": spec.id,
                            "subagent_type": actor.name,
                            "description": message[:200],
                            "status": "success",
                            "duration_ms": duration_ms,
                            "toolCalls": [],
                            "output": result_text[:1000] if result_text else None,
                        }
                    ]
                    # Create AIMessage with metadata in additional_kwargs
                    ai_message = AIMessage(
                        content=result_text,
                        additional_kwargs={
                            "thinking_steps": thinking_steps,
                            "spawned_tasks": spawned_tasks,
                            "display_scenario": "agent",
                        }
                    )
                    await history_graph.aupdate_state(
                        config,
                        {"messages": [HumanMessage(content=message), ai_message]}
                    )
                    logger.info(f"[_handle_delegate] Persisted messages with metadata to checkpoint")
            except Exception as e:
                logger.warning(f"[_handle_delegate] Failed to persist messages: {e}")

        except ValueError as e:
            # Agent not found error
            logger.error(f"Delegate failed: {e}")
            yield _format_sse(
                "text_delta",
                {"text": f"抱歉，无法找到合适的代理来处理此请求：{str(e)}"},
                event_id,
            )

        except Exception as e:
            # General execution error
            logger.exception(f"Delegate execution failed: {e}")
            if spec.id in self.progress_manager.progress.items:
                self.progress_manager.fail_task(spec.id, str(e))
                yield _format_sse(
                    "task_completed",
                    {
                        "task_id": spec.id,
                        "status": "error",
                        "error": str(e),
                    },
                    event_id,
                )
            else:
                yield _format_sse(
                    "text_delta",
                    {"text": f"抱歉，执行任务时出错：{str(e)}"},
                    event_id,
                )

    def _parse_workflow_steps(self, content: str) -> list[dict[str, str]]:
        """Parse workflow steps from command markdown.

        Steps are located under the `## workflow` or `## 工作流程` section:

        ## workflow

        ### 1. 理解问题
        解析用户的问题并确定...

        ### 2. 获取数据
        优先级 1: ...

        ## 示例  <-- workflow section ends here

        Returns:
            List of {"id": "step_1", "title": "理解问题", "content": "..."}
        """
        import re

        # 1. Find the ## workflow or ## 工作流程 section (supports both EN and CN)
        workflow_match = re.search(
            r'^##\s*(workflow|工作流程)\s*$', content, re.MULTILINE | re.IGNORECASE
        )
        if not workflow_match:
            return []

        workflow_start = workflow_match.end()

        # 2. Find where workflow section ends (next ## heading or end of content)
        next_section = re.search(r'^##\s+[^#]', content[workflow_start:], re.MULTILINE)
        if next_section:
            workflow_end = workflow_start + next_section.start()
        else:
            workflow_end = len(content)

        workflow_content = content[workflow_start:workflow_end]

        # 3. Parse ### N. Title steps within workflow section
        step_pattern = r'###\s*(\d+)[\.、]\s*(.+?)(?=\n)'
        matches = list(re.finditer(step_pattern, workflow_content))

        if not matches:
            return []

        steps = []
        for i, match in enumerate(matches):
            step_num = match.group(1)
            step_title = match.group(2).strip()
            start_pos = match.end()

            # Content ends at next step or end of workflow section
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(workflow_content)

            step_content = workflow_content[start_pos:end_pos].strip()

            steps.append({
                "id": f"step_{step_num}",
                "title": step_title,
                "content": step_content,
            })

        return steps

    def _step_needs_context(self, step_content: str, context_type: str) -> bool:
        """Determine if a step needs specific context type.

        Args:
            step_content: The content/description of the step
            context_type: Either 'files' or 'skills'

        Returns:
            True if the step needs this context type
        """
        content_lower = step_content.lower()

        if context_type == "files":
            # Keywords indicating step needs file access
            keywords = [
                "文件",
                "数据",
                "csv",
                "excel",
                "读取",
                "read",
                "file",
                "探查",
                "profiler",
                "收集",
                "加载",
                "load",
                "parse",
                "解析",
            ]
            return any(kw in content_lower for kw in keywords)
        elif context_type == "skills":
            # Keywords indicating step needs skill instructions
            keywords = [
                "技能",
                "skill",
                "代码",
                "python",
                "执行",
                "execute",
                "profiler",
                "探查",
                "分析",
                "处理",
            ]
            return any(kw in content_lower for kw in keywords)
        return True  # Default to injecting

    def _get_allowed_actions(self, step: dict[str, str]) -> str:
        """Generate allowed actions list based on step content.

        Args:
            step: Step dictionary with 'content' key

        Returns:
            Formatted string of allowed actions
        """
        content = step["content"].lower()
        allowed = []

        if any(kw in content for kw in ["读取", "read", "文件", "csv", "excel", "file"]):
            allowed.append("- 读取文件内容")
        if any(kw in content for kw in ["python", "代码", "执行", "execute", "profiler"]):
            allowed.append("- 执行 Python 代码")
        if any(kw in content for kw in ["查询", "sql", "数据库", "database"]):
            allowed.append("- 执行数据库查询")

        return "\n".join(allowed) if allowed else "- 仅分析和输出文本"

    def _get_forbidden_actions(
        self, step: dict[str, str], step_index: int, total_steps: int
    ) -> str:
        """Generate forbidden actions list based on step content.

        Args:
            step: Step dictionary with 'content' key
            step_index: 0-based index of current step
            total_steps: Total number of steps

        Returns:
            Formatted string of forbidden actions
        """
        content = step["content"].lower()
        forbidden = []

        # If step doesn't involve data operations, forbid file reading and code execution
        if not any(
            kw in content for kw in ["读取", "read", "文件", "csv", "excel", "file", "收集", "探查"]
        ):
            forbidden.append("- 不要读取文件")
        if not any(
            kw in content for kw in ["python", "代码", "执行", "execute", "profiler", "处理"]
        ):
            forbidden.append("- 不要执行 Python 代码")
        if not any(kw in content for kw in ["查询", "sql", "数据库", "database"]):
            forbidden.append("- 不要执行数据库查询")

        # Always forbid executing subsequent steps
        if step_index < total_steps - 1:
            forbidden.append(f"- 不要执行步骤 {step_index + 2} 及之后的工作")

        return "\n".join(forbidden) if forbidden else "- 无特殊限制"

    async def _execute_command_steps(
        self,
        command_name: str,
        user_args: str,
        workflow_steps: list[dict[str, str]],
        agent_name: str | None,
        thread_id: str,
        event_id: int,
        file_section: str = "",
        skill_instructions: str = "",
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute command workflow steps sequentially.

        Creates SubtaskSpecs for each step and executes them in order,
        passing context between steps.

        Args:
            command_name: Name of the command being executed
            user_args: User's arguments to the command
            workflow_steps: List of parsed workflow steps
            agent_name: Optional explicit agent name
            thread_id: Thread ID (original, used for persisting final result)
            event_id: Starting event ID
            file_section: Optional file context section
            skill_instructions: Optional skill instructions to inject

        Yields:
            SSE events for each step execution
        """
        # Create independent thread_id for command execution to avoid loading full history
        # This significantly reduces prompt tokens (from ~100k to ~10k)
        command_thread_id = f"cmd-{command_name}-{uuid4().hex[:8]}"

        # 1. Create SubtaskSpecs for each step
        logger.info(
            f"[_execute_command_steps] Creating {len(workflow_steps)} subtasks, "
            f"skill_instructions present: {bool(skill_instructions)}, len={len(skill_instructions)}"
        )
        total_steps = len(workflow_steps)
        subtasks: list[SubtaskSpec] = []
        for i, step in enumerate(workflow_steps):
            # Determine if this step needs file and skill context
            step_needs_files = self._step_needs_context(step["content"], "files")
            step_needs_skills = self._step_needs_context(step["content"], "skills")

            # Only inject context when needed
            current_file_section = file_section if step_needs_files else ""
            current_skill_instructions = skill_instructions if step_needs_skills else ""

            # Get allowed and forbidden actions for this step
            allowed_actions = self._get_allowed_actions(step)
            forbidden_actions = self._get_forbidden_actions(step, i, total_steps)

            logger.info(
                f"[_execute_command_steps] Step {i+1}: needs_files={step_needs_files}, "
                f"needs_skills={step_needs_skills}"
            )

            step_description = f"""## 命令: /{command_name} - 步骤 {step['id']} (共 {total_steps} 步)

## 用户原始请求
{user_args}
{current_file_section}
## 当前步骤: {step['title']}

{step['content']}
{current_skill_instructions}
## 步骤边界约束 [必须遵守]

**此步骤的目标**: {step['title']}

**允许的操作**:
- 分析和理解信息
- 生成文本输出
{allowed_actions}

**禁止的操作**:
{forbidden_actions}

**输出要求**:
- 只输出此步骤的结果
- 不要预先执行后续步骤的工作
- 如果需要的信息不足，说明缺少什么，而不是自行获取
"""
            logger.info(
                f"[_execute_command_steps] Step {i+1} description length: {len(step_description)}, "
                f"has skill_instructions: {bool(current_skill_instructions)}"
            )
            spec = SubtaskSpec(
                id=f"cmd-{command_name}-{step['id']}-{uuid4().hex[:8]}",
                description=step_description,
                explicit_agent=agent_name,
                depends_on=[subtasks[i - 1].id] if i > 0 else [],
            )
            subtasks.append(spec)

        # 2. Add all subtasks to progress manager
        for spec in subtasks:
            self.progress_manager.add_task(spec)

        # 3. Select actor once (all steps use same agent)
        actor = await self.actor_factory.select_actor(subtasks[0])

        # 4. Emit thinking event with step count
        yield _format_sse(
            "thinking",
            {
                "content": f"执行命令 /{command_name}，共 {len(subtasks)} 个步骤",
                "type": "command",
            },
            event_id,
        )
        event_id += 1

        # 5. Emit task_spawned events for all steps
        for i, spec in enumerate(subtasks):
            step = workflow_steps[i]
            yield _format_sse(
                "task_spawned",
                {
                    "task_id": spec.id,
                    "subagent_type": actor.name,
                    "description": f"步骤 {i + 1}: {step['title']}",
                    "status": "pending",
                },
                event_id,
            )
            event_id += 1

        # 6. Execute steps sequentially
        accumulated_context = ""
        all_results: list[dict[str, Any]] = []
        start_time = time.time()

        for i, spec in enumerate(subtasks):
            step = workflow_steps[i]
            step_start_time = time.time()

            # Emit task_started
            yield _format_sse("task_started", {"task_id": spec.id}, event_id)
            event_id += 1

            self.progress_manager.start_task(spec.id, actor.name)

            # Build prompt with accumulated context from previous steps
            task_message = spec.description
            if accumulated_context:
                task_message += f"\n\n## 前序步骤结果\n\n{accumulated_context}"

            # Get context prompt if available
            context_prompt = None
            if self._current_context:
                context_prompt = self._current_context.build_context_prompt()

            # Execute step using command_thread_id to avoid loading full history
            result_text = ""
            tool_outputs: list[str] = []  # Collect tool outputs for context
            async for event in self._execute_actor(
                actor,
                task_message,
                command_thread_id,
                event_id,
                task_id=spec.id,
                user_id=self._current_user_id,
                system_context=context_prompt,
            ):
                event_id += 1
                event_type = event.get("event")

                if event_type == "text_delta":
                    data = json.loads(event.get("data", "{}"))
                    text_chunk = data.get("text", "")
                    result_text += text_chunk
                    yield _format_sse(
                        "task_output",
                        {"task_id": spec.id, "text": text_chunk},
                        event_id,
                    )
                elif event_type in ("tool_call_start", "tool_call_result"):
                    data = json.loads(event.get("data", "{}"))
                    data["task_id"] = spec.id
                    yield _format_sse(str(event_type), data, event_id)

                    # Collect data-related tool outputs for context passing
                    if event_type == "tool_call_result":
                        tool_name = data.get("name", "")
                        tool_output = data.get("output", "")
                        if tool_name in ("execute_python", "execute_python_with_input") and tool_output:
                            tool_outputs.append(tool_output)

            # Complete step
            step_duration_ms = int((time.time() - step_start_time) * 1000)
            self.progress_manager.complete_task(spec.id, result_text)

            # Emit task_completed
            yield _format_sse(
                "task_completed",
                {
                    "task_id": spec.id,
                    "status": "success",
                    "duration_ms": step_duration_ms,
                },
                event_id,
            )
            event_id += 1

            # Track result for history
            all_results.append({
                "task_id": spec.id,
                "subagent_type": actor.name,
                "description": f"步骤 {i + 1}: {step['title']}",
                "status": "success",
                "duration_ms": step_duration_ms,
                "toolCalls": [],
                "output": result_text[:1000] if result_text else None,
            })

            # Add to accumulated context for next step (limit to prevent context overflow)
            # Include tool outputs when available for better context passing
            if tool_outputs:
                tool_context = "\n\n---\n\n".join(tool_outputs)[:4000]
                accumulated_context += f"\n### {step['title']}\n{result_text[:1500]}\n\n### 工具执行结果\n{tool_context}\n"
            else:
                accumulated_context += f"\n### {step['title']}\n{result_text[:2000]}\n"

            logger.info(
                f"[_execute_command_steps] Step {i + 1}/{len(subtasks)} completed - "
                f"task_id={spec.id[:8]}, duration_ms={step_duration_ms}"
            )

        # 7. Persist to checkpoint
        total_duration_ms = int((time.time() - start_time) * 1000)
        try:
            from backend.checkpointer_store import get_history_graph
            from langchain_core.runnables.config import RunnableConfig

            history_graph = get_history_graph()
            if history_graph:
                config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
                thinking_steps = [
                    {
                        "type": "routing",
                        "content": f"执行命令 /{command_name}，共 {len(subtasks)} 个步骤",
                        "timestamp": int(time.time() * 1000),
                    }
                ]
                # Combine all step results for final output
                final_result = "\n\n".join(
                    f"### {workflow_steps[i]['title']}\n{r['output'] or ''}"
                    for i, r in enumerate(all_results)
                )
                ai_message = AIMessage(
                    content=final_result[:5000],
                    additional_kwargs={
                        "thinking_steps": thinking_steps,
                        "spawned_tasks": all_results,
                        "display_scenario": "agent",
                    },
                )
                # Reconstruct original message
                original_message = f"/{command_name} {user_args}" if user_args else f"/{command_name}"
                await history_graph.aupdate_state(
                    config,
                    {"messages": [HumanMessage(content=original_message), ai_message]},
                )
                logger.info(
                    f"[_execute_command_steps] Persisted {len(subtasks)} steps to checkpoint"
                )
        except Exception as e:
            logger.warning(f"[_execute_command_steps] Failed to persist messages: {e}")

        logger.info(
            f"[_execute_command_steps] Completed /{command_name} - "
            f"steps={len(subtasks)}, total_duration_ms={total_duration_ms}"
        )

        # 8. Output final result to user (text_delta -> message.content)
        # Try using the last step's output (typically "展示发现" step)
        # If last step has no output, merge all step outputs
        if all_results:
            final_output = all_results[-1].get("output", "")

            if not final_output:
                # Last step has no output, merge all steps with output
                outputs = [r.get("output", "") for r in all_results if r.get("output")]
                final_output = "\n\n---\n\n".join(outputs) if outputs else ""

            if final_output:
                yield _format_sse(
                    "text_delta",
                    {"text": final_output},
                    event_id,
                )

    async def _handle_command(
        self,
        message: str,
        thread_id: str,
        intent: IntentResult,
        start_event_id: int,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Handle command action - execute user-invoked /command.

        Validates plugin permissions and delegates to the command's agent
        with the command workflow injected.

        Args:
            message: User message (e.g., "/analyze 过去30天的用户数据")
            thread_id: Thread ID
            intent: Intent with command_name and plugin_name
            start_event_id: Starting event ID

        Yields:
            SSE events (thinking, task_spawned, text_delta, task_completed)
        """
        from backend.commands import COMMAND_REGISTRY
        from backend.plugins.service import is_plugin_enabled

        event_id = start_event_id
        command_name = intent.command_name
        plugin_name = intent.plugin_name

        logger.info(
            f"[_handle_command] Starting - command={command_name}, "
            f"plugin={plugin_name}"
        )

        # 1. Check if the plugin is enabled for this user
        if self._current_user_id and plugin_name:
            from uuid import UUID
            user_uuid = UUID(self._current_user_id) if isinstance(self._current_user_id, str) else self._current_user_id
            enabled = await is_plugin_enabled(user_uuid, plugin_name)
            if not enabled:
                logger.warning(
                    f"[_handle_command] Plugin not enabled: {plugin_name}"
                )
                yield _format_sse(
                    "text_delta",
                    {
                        "text": f"命令 /{command_name} 所属的插件 {plugin_name} 未启用。"
                        "请在设置中启用该插件。"
                    },
                    event_id,
                )
                return

        # 2. Get the command
        if not command_name or command_name not in COMMAND_REGISTRY:
            yield _format_sse(
                "error",
                {"message": f"未知命令: /{command_name}"},
                event_id,
            )
            return

        command = COMMAND_REGISTRY[command_name]

        # 3. Load command content (workflow)
        command_content = command.load_content()

        # 3.5 Inject skill instructions if command declares skills
        skill_instructions = ""
        if command.skills:
            from backend.skills.registry import SKILL_REGISTRY
            logger.info(f"[_handle_command] Command skills: {command.skills}")
            logger.info(f"[_handle_command] SKILL_REGISTRY keys: {list(SKILL_REGISTRY.keys())}")
            for skill_name in command.skills:
                if skill_name in SKILL_REGISTRY:
                    skill = SKILL_REGISTRY[skill_name]
                    instructions = skill.load_instructions()
                    skill_instructions += f"\n\n## [Skill: {skill_name}]\n{instructions}\n"
                    logger.info(f"[_handle_command] Injected skill: {skill_name}, len={len(instructions)}")
                else:
                    logger.warning(
                        f"[_handle_command] Skill not found: {skill_name}"
                    )
            logger.info(f"[_handle_command] Total skill_instructions length: {len(skill_instructions)}")
        else:
            logger.info(f"[_handle_command] No skills declared for command")

        # 4. Extract user arguments (remove /command prefix)
        user_args = message.split(maxsplit=1)[1] if " " in message else ""

        # 5. Build file section if files are available in context
        # This ensures LLM sees the files in the same message as the workflow instructions
        file_section = ""
        if self._current_context and self._current_context.files.files:
            file_prompt = self._current_context.files.to_prompt()
            file_section = f"""

## 可用文件（已提供，直接使用）

{file_prompt}

**重要**: 这些文件已在上下文中提供。请直接使用 `read_file(file_path="路径")` 读取，不要用 `ls`、`find` 或其他命令搜索文件系统。
"""

        # 6. Extract agent name from plugin_name (e.g., "package:data" -> "data")
        agent_name = None
        if plugin_name and ":" in plugin_name:
            agent_name = plugin_name.split(":", 1)[1]

        # 7. Parse workflow steps from command markdown
        workflow_steps = self._parse_workflow_steps(command_content)

        if workflow_steps:
            # Multi-step execution: delegate to _execute_command_steps
            logger.info(
                f"[_handle_command] Found {len(workflow_steps)} workflow steps, "
                f"delegating to step executor"
            )
            logger.info(
                f"[_handle_command] skill_instructions to pass: len={len(skill_instructions)}, "
                f"preview={skill_instructions[:200] if skill_instructions else 'None'}..."
            )
            try:
                async for event in self._execute_command_steps(
                    command_name=command_name,
                    user_args=user_args,
                    workflow_steps=workflow_steps,
                    agent_name=agent_name,
                    thread_id=thread_id,
                    event_id=event_id,
                    file_section=file_section,
                    skill_instructions=skill_instructions,
                ):
                    yield event
            except Exception as e:
                logger.exception(f"Command step execution failed: {e}")
                yield _format_sse(
                    "text_delta",
                    {"text": f"抱歉，执行命令 /{command_name} 时出错：{str(e)}"},
                    event_id,
                )
            return

        # Fallback: single-task execution (no workflow steps found)
        logger.info(
            f"[_handle_command] No workflow steps found, using single-task execution"
        )

        # Build task description with full command content
        task_description = f"""## 命令: /{command_name}

## 用户请求
{user_args}
{file_section}
## 命令说明和工作流程
{command_content}
{skill_instructions}
## 重要
严格按照上述工作流程执行任务。
"""

        logger.info(
            f"[_handle_command] Delegating to agent={agent_name}, "
            f"args='{user_args[:50]}...'"
        )

        # 8. Create SubtaskSpec (single task)
        spec = SubtaskSpec(
            id=str(uuid4()),
            description=task_description,
            explicit_agent=agent_name,
        )

        try:
            # Select actor
            actor = await self.actor_factory.select_actor(spec)
            logger.info(f"[_handle_command] Actor selected: {actor.name}")

            # Emit thinking event
            yield _format_sse(
                "thinking",
                {
                    "content": f"执行命令 /{command_name}...",
                    "type": "command",
                },
                event_id,
            )
            event_id += 1

            # Add task to progress manager
            self.progress_manager.add_task(spec)

            # Emit task_spawned
            yield _format_sse(
                "task_spawned",
                {
                    "task_id": spec.id,
                    "subagent_type": actor.name,
                    "description": f"/{command_name} {user_args[:100]}",
                    "status": "pending",
                },
                event_id,
            )
            event_id += 1

            # Emit task_started
            yield _format_sse(
                "task_started",
                {"task_id": spec.id},
                event_id,
            )
            event_id += 1

            # Start task
            self.progress_manager.start_task(spec.id, actor.name)

            # Get context prompt (if any)
            context_prompt = None
            if self._current_context:
                context_prompt = self._current_context.build_context_prompt()
                logger.info(
                    f"[_handle_command] Context prompt length: "
                    f"{len(context_prompt) if context_prompt else 0}"
                )
                if context_prompt:
                    logger.debug(
                        f"[_handle_command] Context prompt preview: "
                        f"{context_prompt[:200]}..."
                    )
            else:
                logger.warning("[_handle_command] No current context available")

            # Execute actor
            start_time = time.time()
            result_text = ""
            async for event in self._execute_actor(
                actor, task_description, thread_id, event_id,
                task_id=spec.id,
                user_id=self._current_user_id,
                system_context=context_prompt,
            ):
                event_id += 1
                event_type = event.get("event")

                # Handle tool_call events
                if event_type in ("tool_call_start", "tool_call_result"):
                    data = json.loads(event.get("data", "{}"))
                    data["task_id"] = spec.id
                    yield _format_sse(str(event_type), data, event_id)
                # Convert text_delta to task_output
                elif event_type == "text_delta":
                    data = json.loads(event.get("data", "{}"))
                    text_chunk = data.get("text", "")
                    result_text += text_chunk
                    yield _format_sse(
                        "task_output",
                        {"task_id": spec.id, "text": text_chunk},
                        event_id,
                    )
                else:
                    yield event

            # Complete task
            duration_ms = int((time.time() - start_time) * 1000)
            self.progress_manager.complete_task(spec.id, "completed")
            logger.info(
                f"[_handle_command] Completed - task_id={spec.id[:8]}, "
                f"duration_ms={duration_ms}"
            )

            yield _format_sse(
                "task_completed",
                {
                    "task_id": spec.id,
                    "status": "success",
                    "duration_ms": duration_ms,
                },
                event_id,
            )
            event_id += 1

            # Output final result
            if result_text:
                yield _format_sse(
                    "text_delta",
                    {"text": f"\n\n{result_text}"},
                    event_id,
                )

            # Persist command metadata to checkpoint for history retrieval
            try:
                from backend.checkpointer_store import get_history_graph
                from langchain_core.runnables.config import RunnableConfig
                history_graph = get_history_graph()
                if history_graph:
                    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
                    # Build thinking_steps from the command event
                    thinking_steps = [
                        {
                            "type": "routing",
                            "content": f"执行命令 /{command_name}...",
                            "timestamp": int(time.time() * 1000),
                        }
                    ]
                    # Build spawned_tasks
                    spawned_tasks = [
                        {
                            "task_id": spec.id,
                            "subagent_type": actor.name,
                            "description": f"/{command_name} {user_args[:100]}",
                            "status": "success",
                            "duration_ms": duration_ms,
                            "toolCalls": [],
                            "output": result_text[:1000] if result_text else None,
                        }
                    ]
                    # Create AIMessage with metadata in additional_kwargs
                    ai_message = AIMessage(
                        content=result_text,
                        additional_kwargs={
                            "thinking_steps": thinking_steps,
                            "spawned_tasks": spawned_tasks,
                            "display_scenario": "agent",
                        }
                    )
                    await history_graph.aupdate_state(
                        config,
                        {"messages": [HumanMessage(content=message), ai_message]}
                    )
                    logger.info(f"[_handle_command] Persisted messages with metadata to checkpoint")
            except Exception as e:
                logger.warning(f"[_handle_command] Failed to persist messages: {e}")

        except ValueError as e:
            logger.error(f"Command execution failed: {e}")
            yield _format_sse(
                "text_delta",
                {"text": f"抱歉，无法找到合适的代理来处理命令 /{command_name}：{str(e)}"},
                event_id,
            )

        except Exception as e:
            logger.exception(f"Command execution failed: {e}")
            if spec.id in self.progress_manager.progress.items:
                self.progress_manager.fail_task(spec.id, str(e))
                yield _format_sse(
                    "task_completed",
                    {
                        "task_id": spec.id,
                        "status": "error",
                        "error": str(e),
                    },
                    event_id,
                )
            else:
                yield _format_sse(
                    "text_delta",
                    {"text": f"抱歉，执行命令 /{command_name} 时出错：{str(e)}"},
                    event_id,
                )

    async def _execute_actor(
        self,
        actor: Actor,
        message: str,
        thread_id: str,
        start_event_id: int,
        task_id: str | None = None,
        user_id: str | None = None,
        system_context: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute actor and stream response.

        Args:
            actor: Actor to execute
            message: User message (clean, without context injection)
            thread_id: Thread ID
            start_event_id: Starting event ID
            task_id: Optional parent task ID for associating tool calls with this task
            user_id: Optional user ID for file registration and permissions
            system_context: Optional context information to pass as SystemMessage.
                           This avoids polluting user message history with metadata.

        Yields:
            SSE events from actor execution
        """
        from backend.stream_handler import stream_agent_response

        event_id = start_event_id

        if actor.graph is None:
            # Fallback for minimal actor (shouldn't happen)
            yield _format_sse(
                "text_delta",
                {"text": "抱歉，该代理暂时不可用。"},
                event_id,
            )
            return

        # Create Langfuse span for actor execution
        # NOTE: Using start_span() instead of start_as_current_observation() to avoid
        # context loss issues with async generators. The OpenTelemetry context is lost
        # after yield statements, making update_current_observation() ineffective.
        # See: https://github.com/langfuse/langfuse/issues/7226
        langfuse_service = get_langfuse_service()
        langfuse_client = langfuse_service.get_client() if langfuse_service.enabled else None
        span = None  # Direct span object reference (not context manager)

        if langfuse_client:
            try:
                # Use start_span to get an independent span object
                # This allows direct update() and end() calls without context dependency
                span = langfuse_client.start_span(
                    name=f"actor-execution-{actor.name}",
                    input={
                        "actor_name": actor.name,
                        "message_preview": message[:200] if message else None,
                        "task_id": task_id,
                    },
                )
            except Exception:
                pass

        # Stream from the actor's graph using existing stream_handler
        error_occurred = None
        collected_output = ""  # Collect text_delta events for Langfuse output
        collected_tools: list[dict[str, Any]] = []  # Collect tool call info
        event_count = 0  # Track event count
        try:
            logger.info(
                f"[_execute_actor] Starting stream for actor={actor.name}, "
                f"message_len={len(message)}, task_id={task_id}"
            )
            async for event in stream_agent_response(
                agent=actor.graph,
                thread_id=thread_id,
                message=message,
                task_id=task_id,
                user_id=user_id,
                system_context=system_context,
            ):
                # Re-emit events (excluding done, we handle that ourselves)
                if event.get("event") != "done":
                    event_type = event.get("event")
                    event_count += 1

                    # Log event types for debugging (first 10 events to avoid spam)
                    if event_count <= 10:
                        logger.debug(f"[_execute_actor] Event {event_count}: type={event_type}")

                    # Collect text_delta content for Langfuse span output
                    if event_type == "text_delta":
                        try:
                            data = json.loads(event.get("data", "{}"))
                            collected_output += data.get("text", "")
                        except Exception:
                            pass

                    # Collect tool call info
                    elif event_type == "tool_call_start":
                        try:
                            data = json.loads(event.get("data", "{}"))
                            collected_tools.append({
                                "name": data.get("name"),
                                "id": data.get("id"),
                            })
                        except Exception:
                            pass

                    yield event
                    event_id += 1

            logger.info(
                f"[_execute_actor] Stream completed for actor={actor.name}, "
                f"event_count={event_count}, output_len={len(collected_output)}"
            )

        except Exception as e:
            error_occurred = e
            logger.exception(f"Error executing actor {actor.name}: {e}")
            yield _format_sse(
                "text_delta",
                {"text": f"执行代理 {actor.name} 时出错：{str(e)}"},
                event_id,
            )

        finally:
            # Close Langfuse span using direct span.update() and span.end()
            # This avoids context loss issues with async generators
            if span:
                try:
                    if error_occurred:
                        span.update(output={"error": str(error_occurred)})
                    else:
                        # Build richer output data
                        output_data: dict[str, Any] = {
                            "status": "completed",
                            "event_count": event_count,
                        }

                        # Add text output if available
                        if collected_output:
                            output_data["text"] = collected_output[:1000]

                        # Add tool call summary if available
                        if collected_tools:
                            output_data["tools_used"] = [t["name"] for t in collected_tools[:10]]
                            output_data["tool_count"] = len(collected_tools)

                        span.update(output=output_data)

                    # Explicitly end the span
                    span.end()
                except Exception as e:
                    logger.warning(f"Failed to update/end Langfuse span: {e}")

    async def _handle_plan(
        self,
        message: str,
        thread_id: str,
        intent: IntentResult,
        start_event_id: int,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Handle plan action - decompose into subtasks and execute.

        Workflow:
        1. Use LLM to decompose task into subtasks
        2. Create SubtaskSpecs with dependencies
        3. Run execution loop (process ready tasks)
        4. Aggregate results and generate final response

        Args:
            message: User message
            thread_id: Thread ID
            intent: Analyzed intent
            start_event_id: Starting event ID

        Yields:
            SSE events for all subtask executions
        """
        logger.info("[_handle_plan] Starting task decomposition and execution")
        event_id = start_event_id

        # Reset replanning flag for this plan execution
        self._has_replanned = False

        # Emit thinking event (planning phase)
        yield _format_sse(
            "thinking",
            {
                "content": "分析任务复杂度，进行任务分解...",
                "type": "planning",
            },
            event_id,
        )
        event_id += 1

        try:
            # Step 1: Decompose task into subtasks
            subtasks = await self._decompose_task(message)

            if not subtasks:
                # Fallback to delegate if decomposition fails
                logger.warning("Task decomposition returned no subtasks, falling back to delegate")
                async for event in self._handle_delegate(
                    message, thread_id, intent, event_id
                ):
                    yield event
                return

            logger.info(
                f"[_handle_plan] Decomposition complete - {len(subtasks)} subtasks created"
            )

            # Step 2: Add all subtasks to progress manager and emit all task_spawned (pending)
            # Pre-select actors for all subtasks to emit all tasks at once
            task_actors: dict[str, Actor] = {}
            for spec in subtasks:
                self.progress_manager.add_task(spec)
                try:
                    actor = await self.actor_factory.select_actor(spec)
                    task_actors[spec.id] = actor
                except ValueError as e:
                    logger.error(f"Failed to select actor for {spec.id}: {e}")
                    self.progress_manager.fail_task(spec.id, str(e))

            # Emit thinking event with task list summary (shows task decomposition result)
            task_list_lines = ["任务分解完成:"]
            for i, spec in enumerate(subtasks, 1):
                actor = task_actors.get(spec.id)
                actor_name = actor.name if actor else "unknown"
                # Truncate description to first 50 characters
                desc_preview = spec.description[:50] + ("..." if len(spec.description) > 50 else "")
                task_list_lines.append(f"{i}. {actor_name}: {desc_preview}")

            yield _format_sse(
                "thinking",
                {
                    "content": "\n".join(task_list_lines),
                    "type": "planning",
                },
                event_id,
            )
            event_id += 1

            # Emit all task_spawned events with pending status (show all tasks at once)
            for spec in subtasks:
                if spec.id in task_actors:
                    actor = task_actors[spec.id]
                    yield _format_sse(
                        "task_spawned",
                        {
                            "task_id": spec.id,
                            "subagent_type": actor.name,
                            "description": spec.description[:200],
                            "status": "pending",
                        },
                        event_id,
                    )
                    event_id += 1

            # Step 3: Execution loop
            max_parallel = 3
            results: dict[str, Any] = {}
            loop_round = 0

            while not self.progress_manager.is_all_completed():
                loop_round += 1
                ready_tasks = self.progress_manager.get_ready_tasks()
                logger.info(
                    f"[plan_loop] Round {loop_round}: {len(ready_tasks)} tasks ready"
                )

                if not ready_tasks:
                    # No ready tasks but not all completed - possible deadlock
                    logger.warning("No ready tasks but execution not complete")
                    break

                # Execute ready tasks (limited parallelism)
                for spec in ready_tasks[:max_parallel]:
                    # Skip if actor selection failed earlier
                    if spec.id not in task_actors:
                        continue

                    actor = task_actors[spec.id]

                    # Prepare context from dependencies using ContextManager
                    context_str = ""
                    if spec.depends_on:
                        context_str = await self.context_manager.prepare_for_task(
                            task_description=spec.description,
                            depends_on=spec.depends_on,
                            thread_id=thread_id,
                            expected_input=spec.expected_input,
                        )

                    # Emit task_started when execution begins
                    yield _format_sse(
                        "task_started",
                        {"task_id": spec.id},
                        event_id,
                    )
                    event_id += 1

                    # Start and execute task
                    self.progress_manager.start_task(spec.id, actor.name)
                    start_time = time.time()
                    logger.info(
                        f"[task:{spec.id[:8]}] Executing with actor '{actor.name}'"
                    )

                    try:
                        # Build prompt with context from ContextManager
                        # Apply TASK_INSTRUCTION_TEMPLATE to instruct agent to declare failures
                        task_message = TASK_INSTRUCTION_TEMPLATE.format(
                            description=spec.description
                        )
                        if context_str:
                            task_message = f"{task_message}\n\n## 上下文信息（来自前置任务的输出）\n\n{context_str}\n\n## 注意\n请基于上述上下文信息完成当前任务，不要要求用户重新提供这些数据。"

                        # Get file context to pass as system_context (not injected into user message)
                        file_context = None
                        if self._current_context:
                            file_context = self._current_context.build_context_prompt()
                            if file_context:
                                logger.info(f"[task:{spec.id[:8]}] Will pass file context as system_context")

                        # Execute and collect output with task_id for tool call association
                        # Pass file_context as system_context to avoid polluting message history
                        result_text = ""
                        async for event in self._execute_actor(
                            actor, task_message, thread_id, event_id,
                            task_id=spec.id,
                            user_id=self._current_user_id,
                            system_context=file_context,
                        ):
                            event_id += 1
                            # Convert text_delta to task_output (associate with specific task)
                            if event.get("event") == "text_delta":
                                data = json.loads(event.get("data", "{}"))
                                text_chunk = data.get("text", "")
                                result_text += text_chunk
                                # Emit task_output instead of text_delta
                                yield _format_sse(
                                    "task_output",
                                    {
                                        "task_id": spec.id,
                                        "text": text_chunk,
                                    },
                                    event_id,
                                )
                            else:
                                # Forward other events (tool_call, etc.) as-is
                                yield event

                        # Check for explicit task failure marker in output
                        duration_ms = int((time.time() - start_time) * 1000)
                        fail_reason = self._extract_fail_reason(result_text)

                        if fail_reason:
                            # Task explicitly declared failure
                            logger.warning(
                                f"[task:{spec.id[:8]}] Failed with reason: {fail_reason}"
                            )
                            self.progress_manager.fail_task(spec.id, fail_reason)

                            yield _format_sse(
                                "task_completed",
                                {
                                    "task_id": spec.id,
                                    "status": "failed",
                                    "error": fail_reason,
                                    "duration_ms": duration_ms,
                                },
                                event_id,
                            )
                            event_id += 1

                            # Check if we should trigger intelligent replanning (max 1 time)
                            if not getattr(self, "_has_replanned", False):
                                self._has_replanned = True

                                yield _format_sse(
                                    "thinking",
                                    {
                                        "content": f"任务失败: {fail_reason}\n正在重新规划替代方案...",
                                        "type": "replanning",
                                    },
                                    event_id,
                                )
                                event_id += 1

                                # Get remaining pending tasks
                                remaining = [
                                    self.progress_manager.progress.get_spec(tid)
                                    for tid, item in self.progress_manager.progress.items.items()
                                    if item.status == "pending"
                                ]
                                remaining = [s for s in remaining if s is not None]

                                # Call LLM to replan
                                new_specs = await self._replan_from_failure(
                                    original_message=message,
                                    failed_spec=spec,
                                    fail_reason=fail_reason,
                                    completed_results=results,
                                    remaining_specs=remaining,
                                )

                                if new_specs:
                                    # Cancel original remaining tasks
                                    for remaining_spec in remaining:
                                        self.progress_manager.progress.mark_cancelled(
                                            remaining_spec.id
                                        )
                                        yield _format_sse(
                                            "task_completed",
                                            {
                                                "task_id": remaining_spec.id,
                                                "status": "cancelled",
                                            },
                                            event_id,
                                        )
                                        event_id += 1

                                    # Add new tasks from replanning
                                    for new_spec in new_specs:
                                        self.progress_manager.add_task(new_spec)
                                        try:
                                            new_actor = await self.actor_factory.select_actor(
                                                new_spec
                                            )
                                            task_actors[new_spec.id] = new_actor

                                            yield _format_sse(
                                                "task_spawned",
                                                {
                                                    "task_id": new_spec.id,
                                                    "subagent_type": new_actor.name,
                                                    "description": new_spec.description[:200],
                                                    "status": "pending",
                                                    "is_replan": True,
                                                },
                                                event_id,
                                            )
                                            event_id += 1
                                        except Exception as actor_err:
                                            logger.error(
                                                f"Failed to select actor for replan task: {actor_err}"
                                            )
                        else:
                            # Task completed successfully
                            self.progress_manager.complete_task(spec.id, result_text)
                            results[spec.id] = result_text

                            # Store result in ContextManager for downstream tasks (T015)
                            await self.context_manager.store(
                                context_id=spec.id,
                                thread_id=thread_id,
                                content=result_text,
                                expected_output=spec.expected_output,
                                metadata={"actor": actor.name, "duration_ms": duration_ms},
                            )

                            logger.info(
                                f"[task:{spec.id[:8]}] Completed - duration_ms={duration_ms}, "
                                f"result_len={len(result_text)}"
                            )

                            yield _format_sse(
                                "task_completed",
                                {
                                    "task_id": spec.id,
                                    "status": "success",
                                    "duration_ms": duration_ms,
                                },
                                event_id,
                            )
                            event_id += 1

                    except Exception as e:
                        logger.exception(f"Task {spec.id} failed with exception: {e}")
                        self.progress_manager.fail_task(spec.id, str(e))

                        # Check if we should retry with re-planning
                        if self.progress_manager.should_retry(spec.id):
                            # Emit re-planning thinking event
                            yield _format_sse(
                                "thinking",
                                {
                                    "content": f"Task failed, attempting alternative approach (retry {self.progress_manager.progress.items[spec.id].retry_count}/3)",
                                    "type": "replanning",
                                },
                                event_id,
                            )
                            event_id += 1

                            # Try re-planning: create alternative subtask
                            alt_spec = await self._create_alternative_subtask(spec, str(e))
                            if alt_spec:
                                self.progress_manager.add_task(alt_spec)
                                logger.info(f"Created alternative subtask {alt_spec.id} for failed {spec.id}")
                        else:
                            # Max retries reached
                            yield _format_sse(
                                "task_completed",
                                {
                                    "task_id": spec.id,
                                    "status": "error",
                                    "error": f"Max retries reached: {str(e)}",
                                },
                                event_id,
                            )
                            event_id += 1

            # Step 4: Generate final summary
            final_content = ""
            if results:
                summary = await self._generate_summary(message, results)
                final_content = f"\n\n## 任务完成\n\n{summary}"
                yield _format_sse(
                    "text_delta",
                    {"text": final_content},
                    event_id,
                )

            # Persist plan metadata to checkpoint for history retrieval
            try:
                from backend.checkpointer_store import get_history_graph
                from langchain_core.runnables.config import RunnableConfig
                history_graph = get_history_graph()
                if history_graph:
                    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

                    # Build thinking_steps from planning events
                    thinking_steps = [
                        {
                            "type": "planning",
                            "content": "分析任务复杂度，进行任务分解...",
                            "timestamp": int(time.time() * 1000),
                        }
                    ]

                    # Build spawned_tasks from progress manager
                    spawned_tasks = []
                    for task_id, item in self.progress_manager.progress.items.items():
                        spec = self.progress_manager.progress.get_spec(task_id)
                        if spec and task_id in task_actors:
                            actor = task_actors[task_id]
                            spawned_tasks.append({
                                "task_id": task_id,
                                "subagent_type": actor.name,
                                "description": spec.description[:200],
                                "status": item.status,
                                "duration_ms": getattr(item, "duration_ms", None),
                                "toolCalls": [],
                                "output": results.get(task_id, "")[:1000] if results.get(task_id) else None,
                            })

                    # Create AIMessage with metadata in additional_kwargs
                    ai_message = AIMessage(
                        content=final_content,
                        additional_kwargs={
                            "thinking_steps": thinking_steps,
                            "spawned_tasks": spawned_tasks,
                            "display_scenario": "planning",
                        }
                    )
                    await history_graph.aupdate_state(
                        config,
                        {"messages": [HumanMessage(content=message), ai_message]}
                    )
                    logger.info(f"[_handle_plan] Persisted messages with metadata to checkpoint")
            except Exception as e:
                logger.warning(f"[_handle_plan] Failed to persist messages: {e}")

        except Exception as e:
            logger.exception(f"Plan execution failed: {e}")
            yield _format_sse(
                "text_delta",
                {"text": f"抱歉，执行任务计划时出错：{str(e)}"},
                event_id,
            )

    async def _decompose_task(self, message: str) -> list[SubtaskSpec]:
        """Decompose a complex task into subtasks using LLM.

        Args:
            message: User's complex task description

        Returns:
            List of SubtaskSpecs with dependencies
        """
        decompose_prompt = """\
你是一个任务分解专家。请将以下复杂任务分解为更小的可执行子任务。

## 任务
{message}

## 输出格式
请用中文描述每个子任务，返回 JSON 数组：
```json
[
  {{
    "id": "step_1",
    "description": "子任务1的中文描述",
    "capabilities": ["capability1"],
    "depends_on": [],
    "expected_input": [],
    "expected_output": ["output_type1", "output_type2"]
  }},
  {{
    "id": "step_2",
    "description": "子任务2的中文描述",
    "capabilities": ["capability2"],
    "depends_on": ["step_1"],
    "expected_input": ["output_type1"],
    "expected_output": ["output_type3"]
  }}
]
```

## 输出类型选项
- financial_report: 财务报告、财报数据
- revenue_data: 营收数据、销售数据
- table: 表格数据
- chart: 图表
- code: 代码片段
- analysis_report: 分析报告
- summary: 摘要总结
- file: 生成的文件
- raw_data: 原始数据

## 规则
- 每个任务必须有唯一的 id（如 step_1, step_2, step_3...）
- 使用 depends_on 引用前面任务的 id（如 ["step_1"]）
- **如果任务 B 需要任务 A 的输出，必须设置 depends_on 并声明 expected_input**
- 能力类型: "web_search", "database", "code_execution", "file_generation"
- **描述必须使用中文**
- 最多5个子任务
"""

        messages = [
            SystemMessage(content=decompose_prompt.format(message=message)),
        ]

        logger.info(f"[_decompose_task] Calling LLM for task decomposition")

        # Create Langfuse span for task decomposition
        # NOTE: Using start_generation() instead of start_as_current_observation() to avoid
        # type checking warnings and ensure consistent span update/end pattern.
        langfuse_service = get_langfuse_service()
        langfuse_client = langfuse_service.get_client() if langfuse_service.enabled else None
        span = None  # Direct span object reference

        if langfuse_client:
            try:
                span = langfuse_client.start_generation(
                    name="task-decomposition",
                    model=getattr(self._model, "model", None) or getattr(self._model, "model_name", "unknown"),
                    input={"message": message[:500]},
                )
            except Exception:
                pass

        try:
            response = await self._model.ainvoke(messages)
            logger.debug("[_decompose_task] LLM response received")

            # Extract token usage from response
            if span and hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                span.update(usage={
                    "input": usage.get("input_tokens", 0),
                    "output": usage.get("output_tokens", 0),
                    "total": usage.get("total_tokens", 0),
                })

            content = response.content if hasattr(response, "content") else str(response)
            result_text = str(content) if not isinstance(content, str) else content

            # Parse JSON
            json_str = result_text
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            subtasks_data = json.loads(json_str.strip())

            # Convert to SubtaskSpecs
            specs: list[SubtaskSpec] = []
            id_map: dict[str, str] = {}  # step_id -> uuid

            for task_data in subtasks_data[:5]:  # Max 5 subtasks
                # Get step_id from LLM response, fallback to generated id
                step_id = task_data.get("id", f"step_{len(id_map) + 1}")
                task_uuid = str(uuid4())
                id_map[step_id] = task_uuid

                # Convert string id dependencies to task UUIDs
                depends_on = []
                for dep_id in task_data.get("depends_on", []):
                    # Ensure dep_id is string for consistent lookup
                    dep_id_str = str(dep_id)
                    if dep_id_str in id_map:
                        depends_on.append(id_map[dep_id_str])
                    else:
                        logger.warning(f"[_decompose_task] Unknown dependency: {dep_id}")

                specs.append(
                    SubtaskSpec(
                        id=task_uuid,
                        description=task_data.get("description", ""),
                        capabilities=task_data.get("capabilities", []),
                        depends_on=depends_on,
                        expected_input=task_data.get("expected_input", []),
                        expected_output=task_data.get("expected_output", []),
                    )
                )

            logger.info(f"[_decompose_task] Created {len(specs)} subtasks")

            # Update Langfuse span with output
            if span:
                try:
                    span.update(output={
                        "subtask_count": len(specs),
                        "subtasks": [s.description[:100] for s in specs],
                    })
                except Exception:
                    pass

            return specs

        except Exception as e:
            logger.warning(f"[_decompose_task] Failed: {e}")
            # Update Langfuse span with error
            if span:
                try:
                    span.update(output={"error": str(e)})
                except Exception:
                    pass
            return []

        finally:
            if span:
                try:
                    span.end()
                except Exception:
                    pass

    async def _generate_summary(
        self, original_task: str, results: dict[str, Any]
    ) -> str:
        """Generate a clean summary using LLM aggregation, preserving file download links.

        Args:
            original_task: Original user request
            results: Dict of task_id to result

        Returns:
            Summary text with file links appended
        """
        import re

        if not results:
            return "没有可用的结果。"

        # Extract all file download links
        file_links: list[str] = []
        file_pattern = r'\[.*?下载.*?\]\(/api/files/[^)]+\)'

        # Build context for LLM
        context_parts = []
        for i, (_, result) in enumerate(results.items(), 1):
            if result:
                result_str = str(result)
                # Extract file links
                links = re.findall(file_pattern, result_str)
                file_links.extend(links)
                # Add task result (remove file links to avoid duplication)
                clean_result = re.sub(file_pattern, '[文件已生成]', result_str)
                context_parts.append(f"子任务{i}结果:\n{clean_result[:1000]}")

        summary_prompt = f"""\
基于以下子任务的执行结果，为用户生成一个简洁、结构化的最终回答。

## 原始任务
{original_task}

## 子任务执行结果
{chr(10).join(context_parts)}

## 要求
- 直接回答用户的问题
- 不要提及"子任务"或执行过程
- 使用 markdown 格式
- 简洁明了，突出关键信息
- 如果有数据或发现，用结构化方式呈现
"""

        # Create Langfuse span for summary generation
        # NOTE: Using start_generation() instead of start_as_current_observation() to avoid
        # type checking warnings and ensure consistent span update/end pattern.
        langfuse_service = get_langfuse_service()
        langfuse_client = langfuse_service.get_client() if langfuse_service.enabled else None
        span = None  # Direct span object reference

        if langfuse_client:
            try:
                span = langfuse_client.start_generation(
                    name="summary-generation",
                    model=getattr(self._model, "model", None) or getattr(self._model, "model_name", "unknown"),
                    input={"task": original_task[:200], "result_count": len(results)},
                )
            except Exception:
                pass

        try:
            messages = [SystemMessage(content=summary_prompt)]
            response = await self._model.ainvoke(messages)
            summary = str(response.content)

            # Extract token usage from response
            if span and hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                span.update(usage={
                    "input": usage.get("input_tokens", 0),
                    "output": usage.get("output_tokens", 0),
                    "total": usage.get("total_tokens", 0),
                })

            # Update Langfuse span with output
            if span:
                try:
                    span.update(output={"summary": summary[:500]})
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"LLM summary generation failed: {e}")
            # Update Langfuse span with error
            if span:
                try:
                    span.update(output={"error": str(e)})
                except Exception:
                    pass
            # Fallback to simple summary
            summary = "任务执行完成。"

        finally:
            if span:
                try:
                    span.end()
                except Exception:
                    pass

        # Append file download links at the end
        if file_links:
            summary += "\n\n---\n\n**生成的文件:**\n\n"
            for link in file_links:
                summary += f"- {link}\n"

        return summary

    async def _create_alternative_subtask(
        self, failed_spec: SubtaskSpec, error: str
    ) -> SubtaskSpec | None:
        """Create an alternative subtask when the original fails.

        Uses LLM to generate an alternative approach based on the error.

        Args:
            failed_spec: The failed subtask specification
            error: Error message from the failure

        Returns:
            Alternative SubtaskSpec or None if no alternative possible
        """
        replan_prompt = """\
A task has failed. Suggest an alternative approach.

## Original Task
{description}

## Error
{error}

## Original Capabilities
{capabilities}

## Instructions
Provide an alternative approach as JSON:
```json
{{
  "description": "Alternative task description",
  "capabilities": ["alternative_capability"],
  "approach": "Brief explanation of alternative approach"
}}
```

If no alternative is possible, return:
```json
{{"no_alternative": true, "reason": "explanation"}}
```
"""

        logger.info(
            f"[_create_alternative_subtask] Creating alternative for failed task - "
            f"error='{error[:50]}...'"
        )

        messages = [
            SystemMessage(
                content=replan_prompt.format(
                    description=failed_spec.description,
                    error=error,
                    capabilities=failed_spec.capabilities,
                )
            ),
        ]

        # Create Langfuse span for alternative subtask creation
        # NOTE: Using start_generation() instead of start_as_current_observation() to avoid
        # type checking warnings and ensure consistent span update/end pattern.
        langfuse_service = get_langfuse_service()
        langfuse_client = langfuse_service.get_client() if langfuse_service.enabled else None
        span = None  # Direct span object reference

        if langfuse_client:
            try:
                span = langfuse_client.start_generation(
                    name="create-alternative-subtask",
                    model=getattr(self._model, "model", None) or getattr(self._model, "model_name", "unknown"),
                    input={
                        "original_task": failed_spec.description[:200],
                        "error": error[:200],
                    },
                )
            except Exception:
                pass

        try:
            response = await self._model.ainvoke(messages)

            # Extract token usage from response
            if span and hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                span.update(usage={
                    "input": usage.get("input_tokens", 0),
                    "output": usage.get("output_tokens", 0),
                    "total": usage.get("total_tokens", 0),
                })

            content = response.content if hasattr(response, "content") else str(response)
            result_text = str(content) if not isinstance(content, str) else content

            # Parse JSON
            json_str = result_text
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            if data.get("no_alternative"):
                logger.info(f"No alternative for {failed_spec.id}: {data.get('reason')}")
                # Update Langfuse span
                if span:
                    try:
                        span.update(output={
                            "no_alternative": True,
                            "reason": data.get("reason"),
                        })
                    except Exception:
                        pass
                return None

            # Create alternative subtask
            alt_spec = SubtaskSpec(
                id=str(uuid4()),
                description=data.get("description", failed_spec.description),
                capabilities=data.get("capabilities", []),
                depends_on=failed_spec.depends_on,  # Keep same dependencies
                context={
                    "original_task": failed_spec.description,
                    "error": error,
                    "approach": data.get("approach", ""),
                },
            )

            logger.info(f"Created alternative subtask: {alt_spec.description[:100]}")

            # Update Langfuse span with output
            if span:
                try:
                    span.update(output={
                        "alternative_description": alt_spec.description[:200],
                        "capabilities": alt_spec.capabilities,
                    })
                except Exception:
                    pass

            return alt_spec

        except Exception as e:
            logger.warning(f"Failed to create alternative subtask: {e}")
            # Update Langfuse span with error
            if span:
                try:
                    span.update(output={"error": str(e)})
                except Exception:
                    pass
            return None

        finally:
            if span:
                try:
                    span.end()
                except Exception:
                    pass

    def _extract_fail_reason(self, result_text: str) -> str:
        """Extract failure reason from task output.

        Looks for the [TASK_FAILED] marker and extracts the reason.

        Args:
            result_text: The task output text

        Returns:
            Failure reason string, or empty string if no failure detected
        """
        if TASK_FAILED_MARKER not in result_text:
            return ""

        # Extract content after the marker
        after_marker = result_text.split(TASK_FAILED_MARKER, 1)[1]
        first_line = after_marker.strip().split("\n")[0]

        # Check if it starts with "原因:" and extract the reason
        if first_line.startswith("原因:"):
            return first_line[3:].strip()

        # Otherwise return the first line (up to 200 chars)
        return first_line[:200].strip()

    async def _replan_from_failure(
        self,
        original_message: str,
        failed_spec: SubtaskSpec,
        fail_reason: str,
        completed_results: dict[str, str],
        remaining_specs: list[SubtaskSpec],
    ) -> list[SubtaskSpec]:
        """Replan tasks based on failure reason using LLM.

        When a task fails, this method uses the LLM to generate a new
        set of tasks that can achieve the original goal using a different
        approach.

        Args:
            original_message: User's original request
            failed_spec: The failed task specification
            fail_reason: Reason for the failure
            completed_results: Results from already completed tasks {task_id: result}
            remaining_specs: Remaining pending tasks that haven't been executed

        Returns:
            List of new SubtaskSpecs to replace the failed and remaining tasks
        """
        # Build context for completed tasks
        completed_context = ""
        if completed_results:
            completed_lines = []
            for tid in completed_results.keys():
                item = self.progress_manager.progress.items.get(tid)
                if item:
                    desc = item.description[:50] + ("..." if len(item.description) > 50 else "")
                    completed_lines.append(f"- 已完成: {desc}")
            completed_context = "\n".join(completed_lines)

        # Build context for remaining tasks
        remaining_context = ""
        if remaining_specs:
            remaining_lines = []
            for s in remaining_specs:
                desc = s.description[:50] + ("..." if len(s.description) > 50 else "")
                remaining_lines.append(f"- 待执行: {desc}")
            remaining_context = "\n".join(remaining_lines)

        replan_prompt = f"""\
你是一个任务规划专家。之前的任务执行失败了，请根据失败原因重新规划。

## 用户原始请求
{original_message}

## 失败的任务
{failed_spec.description}

## 失败原因
{fail_reason}

## 已完成的任务
{completed_context or "无"}

## 原计划剩余任务
{remaining_context or "无"}

## 核心原则：降级策略（Graceful Degradation）

当无法获取理想数据时，**必须采用降级方案而非重复尝试相同方式**：

### 数据获取降级路径：
1. **特定 API/数据库** → **网络搜索公开信息**
2. **实时数据** → **历史数据/年报数据**
3. **精确数据** → **公开数据集/行业报告**
4. **完整数据** → **部分可获取的数据 + 说明数据限制**

### 关键要求：
- **不要重复尝试已失败的方法**（如网络搜索失败，不要再次尝试网络搜索相同内容）
- **使用可获取的信息完成任务**，即使信息不完整
- **在最终输出中说明数据来源和限制**，而非因数据不足而失败
- **必须包含最终输出任务**（如PPT、报告等）

### 示例降级：
- "获取特斯拉实时财务数据" 失败 → 改为 "基于公开年报和新闻分析特斯拉财务状况"
- "查询数据库获取销售数据" 失败 → 改为 "使用公开数据集或行业报告估算"
- "获取精确股价" 失败 → 改为 "使用最近可获取的历史数据进行分析"

返回 JSON 数组，格式同原任务分解：
```json
[
  {{
    "id": "step_1",
    "description": "新任务描述（中文）- 明确说明使用的降级方案",
    "capabilities": ["web_search"],
    "depends_on": [],
    "expected_output": ["output_type"]
  }},
  {{
    "id": "step_2",
    "description": "后续任务描述",
    "capabilities": ["file_generation"],
    "depends_on": ["step_1"],
    "expected_output": ["file"]
  }}
]
```

## 输出类型选项
- financial_report: 财务报告、财报数据
- revenue_data: 营收数据、销售数据
- table: 表格数据
- chart: 图表
- code: 代码片段
- analysis_report: 分析报告
- summary: 摘要总结
- file: 生成的文件（如 PPT、PDF、Excel 等）
- raw_data: 原始数据

注意：
- 每个任务必须有唯一的 id（如 step_1, step_2, step_3...）
- depends_on 使用任务的 id 引用（如 ["step_1"]）
- **必须包含原计划中的最终输出任务**
- **使用不同于失败任务的方法**
"""

        messages = [SystemMessage(content=replan_prompt)]

        logger.info(
            f"[_replan_from_failure] Calling LLM for replanning - "
            f"fail_reason='{fail_reason[:50]}...'"
        )

        # Create Langfuse span for replanning
        # NOTE: Using start_generation() instead of start_as_current_observation() to avoid
        # type checking warnings and ensure consistent span update/end pattern.
        langfuse_service = get_langfuse_service()
        langfuse_client = langfuse_service.get_client() if langfuse_service.enabled else None
        span = None  # Direct span object reference

        if langfuse_client:
            try:
                span = langfuse_client.start_generation(
                    name="replan-from-failure",
                    model=getattr(self._model, "model", None) or getattr(self._model, "model_name", "unknown"),
                    input={
                        "original_message": original_message[:200],
                        "failed_task": failed_spec.description[:200],
                        "fail_reason": fail_reason[:200],
                        "completed_count": len(completed_results),
                        "remaining_count": len(remaining_specs),
                    },
                )
            except Exception:
                pass

        try:
            response = await self._model.ainvoke(messages)

            # Extract token usage from response
            if span and hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                span.update(usage={
                    "input": usage.get("input_tokens", 0),
                    "output": usage.get("output_tokens", 0),
                    "total": usage.get("total_tokens", 0),
                })

            content = response.content if hasattr(response, "content") else str(response)
            result_text = str(content) if not isinstance(content, str) else content

            # Parse JSON
            json_str = result_text
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            new_tasks_data = json.loads(json_str.strip())

            # Convert to SubtaskSpec
            new_specs: list[SubtaskSpec] = []
            id_map: dict[str, str] = {}  # step_id -> uuid

            for task_data in new_tasks_data[:5]:  # Max 5 tasks
                # Get step_id from LLM response, fallback to generated id
                step_id = task_data.get("id", f"step_{len(id_map) + 1}")
                task_uuid = str(uuid4())
                id_map[step_id] = task_uuid

                # Convert string id dependencies to task UUIDs
                depends_on = []
                for dep_id in task_data.get("depends_on", []):
                    # Ensure dep_id is string for consistent lookup
                    dep_id_str = str(dep_id)
                    if dep_id_str in id_map:
                        depends_on.append(id_map[dep_id_str])
                    else:
                        logger.warning(f"[_replan_from_failure] Unknown dependency: {dep_id}")

                new_specs.append(
                    SubtaskSpec(
                        id=task_uuid,
                        description=task_data.get("description", ""),
                        capabilities=task_data.get("capabilities", []),
                        depends_on=depends_on,
                        expected_output=task_data.get("expected_output", []),
                        is_replan=True,  # Mark as replanned task
                    )
                )

            logger.info(f"[_replan_from_failure] Generated {len(new_specs)} new tasks")

            # Update Langfuse span with output
            if span:
                try:
                    span.update(output={
                        "new_task_count": len(new_specs),
                        "new_tasks": [s.description[:100] for s in new_specs],
                    })
                except Exception:
                    pass

            return new_specs

        except Exception as e:
            logger.error(f"[_replan_from_failure] Failed: {e}")
            # Update Langfuse span with error
            if span:
                try:
                    span.update(output={"error": str(e)})
                except Exception:
                    pass
            return []

        finally:
            if span:
                try:
                    span.end()
                except Exception:
                    pass
