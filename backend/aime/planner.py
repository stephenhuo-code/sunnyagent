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
from backend.aime.intent import IntentAnalyzer, IntentResult
from backend.aime.models import Actor, SubtaskSpec
from backend.aime.progress_manager import ProgressManager
from backend.llm import get_model

logger = logging.getLogger(__name__)


# Direct reply system prompt for simple queries
_DIRECT_REPLY_PROMPT = """\
You are a helpful AI assistant. Respond to the user's message directly and concisely.

Guidelines:
- Be helpful and friendly
- Keep responses focused and relevant
- Use markdown formatting when appropriate
- For math questions, show the calculation
- For factual questions, provide accurate information
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
    ):
        """Initialize the AIME Planner.

        Args:
            intent_analyzer: Optional custom intent analyzer
            actor_factory: Optional custom actor factory
            progress_manager: Optional custom progress manager
        """
        self.intent_analyzer = intent_analyzer or IntentAnalyzer()
        self.actor_factory = actor_factory or ActorFactory()
        self.progress_manager = progress_manager or ProgressManager()
        self._model = get_model("supervisor")
        logger.info("AIMEPlanner initialized")

    async def process(
        self,
        message: str,
        thread_id: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Process user message and yield SSE events.

        Main entry point for AIME processing. Analyzes intent and
        executes the appropriate action handler.

        Args:
            message: User message
            thread_id: Conversation thread ID
            context: Optional context (may contain explicit_agent, file_ids, etc.)

        Yields:
            SSE event dicts for frontend streaming
        """
        event_id = 0

        # Log entry point
        logger.info(
            f"[process] Starting - thread_id={thread_id}, "
            f"message='{message[:50]}...'"
        )

        try:
            # Analyze user intent
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

        messages = [
            SystemMessage(content=_DIRECT_REPLY_PROMPT),
            HumanMessage(content=message),
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

            # Add task to progress manager and emit task_spawned
            self.progress_manager.add_task(spec)
            yield _format_sse(
                "task_spawned",
                {
                    "task_id": spec.id,
                    "subagent_type": actor.name,
                    "description": message[:200],
                },
                event_id,
            )
            event_id += 1

            # Start task
            self.progress_manager.start_task(spec.id, actor.name)

            # Execute actor
            start_time = time.time()
            async for event in self._execute_actor(
                actor, message, thread_id, event_id
            ):
                event_id += 1
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
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute actor and stream response.

        Args:
            actor: Actor to execute
            message: User message
            thread_id: Thread ID
            start_event_id: Starting event ID

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

            # Step 2: Add all subtasks to progress manager
            for spec in subtasks:
                self.progress_manager.add_task(spec)

            # Emit todos_updated with all subtasks
            yield _format_sse(
                "todos_updated",
                {
                    "todos": self.progress_manager.to_todos(),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
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
                    # Add context from dependencies
                    if spec.depends_on:
                        spec.context = self.progress_manager.get_context_for_task(spec)

                    # Select actor
                    try:
                        actor = self.actor_factory.select_actor(spec)
                    except ValueError as e:
                        logger.error(f"Failed to select actor for {spec.id}: {e}")
                        self.progress_manager.fail_task(spec.id, str(e))
                        continue

                    # Emit task_spawned
                    yield _format_sse(
                        "task_spawned",
                        {
                            "task_id": spec.id,
                            "subagent_type": actor.name,
                            "description": spec.description[:200],
                        },
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
                        # Build prompt with context
                        task_message = spec.description
                        if spec.context:
                            context_str = "\n".join(
                                f"[{k}]: {v}" for k, v in spec.context.items()
                            )
                            task_message = f"{spec.description}\n\n## Context from previous tasks:\n{context_str}"

                        # Execute and collect output
                        result_text = ""
                        async for event in self._execute_actor(
                            actor, task_message, thread_id, event_id
                        ):
                            event_id += 1
                            yield event
                            # Collect text output for context passing
                            if event.get("event") == "text_delta":
                                data = json.loads(event.get("data", "{}"))
                                result_text += data.get("text", "")

                        # Complete task
                        duration_ms = int((time.time() - start_time) * 1000)
                        self.progress_manager.complete_task(spec.id, result_text)
                        results[spec.id] = result_text
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
                        logger.exception(f"Task {spec.id} failed: {e}")
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

                # Emit updated todos
                yield _format_sse(
                    "todos_updated",
                    {
                        "todos": self.progress_manager.to_todos(),
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
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
You are a task decomposition expert. Break down the following complex task into smaller, executable subtasks.

## Task
{message}

## Output Format
Return a JSON array of subtasks:
```json
[
  {{
    "description": "Step 1 description",
    "capabilities": ["capability1"],
    "depends_on": []
  }},
  {{
    "description": "Step 2 description",
    "capabilities": ["capability2"],
    "depends_on": [0]
  }}
]
```

Rules:
- Each subtask should be independently executable
- Use depends_on to reference earlier task indices (0-based)
- Capabilities: "web_search", "database", "code_execution", "file_generation"
- Keep descriptions clear and actionable
- Maximum 5 subtasks
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
            id_map: dict[int, str] = {}

            for i, task_data in enumerate(subtasks_data[:5]):  # Max 5 subtasks
                task_id = str(uuid4())
                id_map[i] = task_id

                # Convert index dependencies to task IDs
                depends_on = []
                for dep_idx in task_data.get("depends_on", []):
                    if dep_idx in id_map:
                        depends_on.append(id_map[dep_idx])

                specs.append(
                    SubtaskSpec(
                        id=task_id,
                        description=task_data.get("description", ""),
                        capabilities=task_data.get("capabilities", []),
                        depends_on=depends_on,
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
        """Generate a summary of completed subtasks.

        Args:
            original_task: Original user request
            results: Dict of task_id to result

        Returns:
            Summary text
        """
        if not results:
            return "没有可用的结果。"

        # Simple summary: list all results
        summary_parts = []
        for i, (task_id, result) in enumerate(results.items(), 1):
            if result:
                preview = str(result)[:500]
                summary_parts.append(f"**子任务 {i}**: {preview}")

        return "\n\n".join(summary_parts) if summary_parts else "所有子任务已完成。"

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
