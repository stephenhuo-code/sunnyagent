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

import json
import logging
import time
from typing import Any, AsyncGenerator
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from backend.aime.actor_factory import ActorFactory
from backend.aime.context import AgentContext
from backend.aime.context_manager import ContextManager
from backend.aime.intent import IntentAnalyzer, IntentResult
from backend.aime.models import Actor, SubtaskSpec
from backend.aime.progress_manager import ProgressManager
from backend.llm import get_model

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
            actor_factory: Optional custom actor factory
            progress_manager: Optional custom progress manager
            context_manager: Optional custom context manager
        """
        self.intent_analyzer = intent_analyzer or IntentAnalyzer()
        self.actor_factory = actor_factory or ActorFactory()
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

        # Log entry point
        logger.info(
            f"[process] Starting - thread_id={thread_id}, "
            f"message='{message[:50]}...'"
        )

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

            else:
                # Fallback to direct reply for unknown actions
                logger.warning(f"Unknown action: {intent.action}, falling back to direct_reply")
                async for event in self._handle_direct_reply(
                    message, thread_id, intent, event_id
                ):
                    event_id += 1
                    yield event

        except Exception as e:
            logger.exception(f"Error in AIMEPlanner.process: {e}")
            yield _format_sse("error", {"message": str(e)}, event_id)
            event_id += 1

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

        # Inject file context if available
        reply_message = message
        if self._current_context:
            context_prompt = self._current_context.build_context_prompt()
            if context_prompt:
                reply_message = f"{context_prompt}\n\n---\n\n{message}"
                logger.info("[_handle_direct_reply] Injected file context")

        messages = [
            SystemMessage(content=_DIRECT_REPLY_PROMPT),
            HumanMessage(content=reply_message),
        ]

        try:
            # Stream response from LLM
            async for chunk in self._model.astream(messages):
                if hasattr(chunk, "content") and chunk.content:
                    yield _format_sse(
                        "text_delta",
                        {"text": chunk.content},
                        event_id,
                    )
                    event_id += 1

        except Exception as e:
            logger.exception(f"Error streaming direct reply: {e}")
            yield _format_sse(
                "text_delta",
                {"text": f"抱歉，生成回复时出错：{str(e)}"},
                event_id,
            )

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
            # Select actor using ActorFactory
            actor = self.actor_factory.select_actor(spec)
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

            # Inject full context at execution time (file metadata with tool hints)
            agent_message = message
            if self._current_context:
                context_prompt = self._current_context.build_context_prompt()
                if context_prompt:
                    agent_message = f"{context_prompt}\n\n---\n\n{message}"
                    logger.info(f"[_handle_delegate] Injected context for execution")

            # Execute actor with task_id for tool call association
            start_time = time.time()
            result_text = ""  # Collect task output for final summary
            async for event in self._execute_actor(
                actor, agent_message, thread_id, event_id,
                task_id=spec.id,
                user_id=self._current_user_id,
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

    async def _execute_actor(
        self,
        actor: Actor,
        message: str,
        thread_id: str,
        start_event_id: int,
        task_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute actor and stream response.

        Args:
            actor: Actor to execute
            message: User message
            thread_id: Thread ID
            start_event_id: Starting event ID
            task_id: Optional parent task ID for associating tool calls with this task
            user_id: Optional user ID for file registration and permissions

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

        # Stream from the actor's graph using existing stream_handler
        try:
            async for event in stream_agent_response(
                agent=actor.graph,
                thread_id=thread_id,
                message=message,
                task_id=task_id,
                user_id=user_id,
            ):
                # Re-emit events (excluding done, we handle that ourselves)
                if event.get("event") != "done":
                    yield event
                    event_id += 1

        except Exception as e:
            logger.exception(f"Error executing actor {actor.name}: {e}")
            yield _format_sse(
                "text_delta",
                {"text": f"执行代理 {actor.name} 时出错：{str(e)}"},
                event_id,
            )

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
                    actor = self.actor_factory.select_actor(spec)
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

                        # Inject file context at execution time (file metadata with tool hints)
                        if self._current_context:
                            file_context = self._current_context.build_context_prompt()
                            if file_context:
                                task_message = f"{file_context}\n\n---\n\n{task_message}"
                                logger.info(f"[task:{spec.id[:8]}] Injected file context for execution")

                        # Execute and collect output with task_id for tool call association
                        result_text = ""
                        async for event in self._execute_actor(
                            actor, task_message, thread_id, event_id,
                            task_id=spec.id,
                            user_id=self._current_user_id,
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
                                            new_actor = self.actor_factory.select_actor(
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
            if results:
                summary = await self._generate_summary(message, results)
                yield _format_sse(
                    "text_delta",
                    {"text": f"\n\n## 任务完成\n\n{summary}"},
                    event_id,
                )

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
        try:
            response = await self._model.ainvoke(messages)
            logger.debug("[_decompose_task] LLM response received")
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
            return specs

        except Exception as e:
            logger.warning(f"[_decompose_task] Failed: {e}")
            return []

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

        try:
            messages = [SystemMessage(content=summary_prompt)]
            response = await self._model.ainvoke(messages)
            summary = str(response.content)
        except Exception as e:
            logger.warning(f"LLM summary generation failed: {e}")
            # Fallback to simple summary
            summary = "任务执行完成。"

        # Append file download links at the end
        if file_links:
            summary += "\n\n---\n\n**生成的文件:**\n\n"
            for link in file_links:
                summary += f"- {link}\n"

        return summary

    def _expand_workflow_skill(self, skill_name: str, message: str) -> list[SubtaskSpec]:
        """Expand a workflow skill into SubtaskSpecs based on its steps.

        Args:
            skill_name: Name of the workflow skill
            message: User message for context

        Returns:
            List of SubtaskSpecs, one per skill step
        """
        from backend.skills.registry import WORKFLOW_SKILLS

        workflow_info = WORKFLOW_SKILLS.get(skill_name)
        if not workflow_info or not workflow_info.steps:
            # Not a workflow skill or no steps defined
            return []

        specs: list[SubtaskSpec] = []
        id_map: dict[str, str] = {}  # step_id -> task_id

        for i, step in enumerate(workflow_info.steps):
            task_id = str(uuid4())
            id_map[step.id] = task_id

            # Build dependencies: each step depends on previous step
            depends_on = []
            if i > 0:
                prev_step_id = workflow_info.steps[i - 1].id
                if prev_step_id in id_map:
                    depends_on.append(id_map[prev_step_id])

            # Build capabilities from step requirement
            capabilities = []
            if step.required_capability:
                capabilities.append(step.required_capability)

            specs.append(
                SubtaskSpec(
                    id=task_id,
                    description=f"[{skill_name}] {step.description}",
                    skill_name=skill_name,
                    skill_step_id=step.id,
                    capabilities=capabilities,
                    depends_on=depends_on,
                    context={"original_message": message},
                )
            )

        logger.info(
            f"Expanded workflow skill '{skill_name}' into {len(specs)} subtasks"
        )
        return specs

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

        try:
            response = await self._model.ainvoke(messages)
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
            return alt_spec

        except Exception as e:
            logger.warning(f"Failed to create alternative subtask: {e}")
            return None

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

        try:
            response = await self._model.ainvoke(messages)
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
            return new_specs

        except Exception as e:
            logger.error(f"[_replan_from_failure] Failed: {e}")
            return []
