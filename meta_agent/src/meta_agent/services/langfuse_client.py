"""Langfuse client for dataset management and trace reading."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from langfuse import Langfuse

logger = logging.getLogger(__name__)


# Data Types


@dataclass
class Trace:
    """Trace summary."""

    id: str
    session_id: str | None = None
    name: str | None = None
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Span:
    """Execution step."""

    id: str
    name: str
    start_time: datetime
    end_time: datetime
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None


@dataclass
class Generation:
    """LLM call."""

    id: str
    model: str
    prompt: str | None = None
    completion: str | None = None
    usage: dict[str, Any] | None = None


@dataclass
class TraceDetail:
    """Trace detail with spans and generations."""

    trace: Trace
    spans: list[Span] = field(default_factory=list)
    generations: list[Generation] = field(default_factory=list)


@dataclass
class ScoreInput:
    """Score input for batch operations."""

    trace_id: str
    name: str
    value: float
    comment: str | None = None


# Exceptions


class LangfuseError(Exception):
    """Langfuse operation error."""

    pass


class LangfuseConnectionError(LangfuseError):
    """Connection error."""

    pass


class LangfuseNotFoundError(LangfuseError):
    """Resource not found."""

    pass


class LangfuseClient:
    """Langfuse client for Meta-Agent.

    Handles:
    - Dataset creation and management
    - Trace reading
    - Score writing
    """

    def __init__(
        self,
        public_key: str = "",
        secret_key: str = "",
        base_url: str = "http://localhost:3001",
    ):
        """
        Initialize Langfuse client.

        Args:
            public_key: Langfuse public key
            secret_key: Langfuse secret key
            base_url: Langfuse API base URL
        """
        self.public_key = public_key
        self.secret_key = secret_key
        self.base_url = base_url
        self._client: Langfuse | None = None

    def _get_client(self) -> Langfuse:
        """Get or create Langfuse client."""
        if self._client is None:
            try:
                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.base_url,
                )
            except Exception as e:
                raise LangfuseConnectionError(f"Failed to connect to Langfuse: {e}")
        return self._client

    # Dataset Operations (Write)

    async def create_dataset(
        self,
        name: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create dataset.

        Args:
            name: Dataset name, format "meta-agent-{plugin}-{version}"
            description: Dataset description
            metadata: Extra metadata

        Returns:
            dataset_id: Langfuse Dataset ID

        Raises:
            LangfuseError: If creation fails
        """
        try:
            client = self._get_client()
            dataset = client.create_dataset(
                name=name,
                description=description,
                metadata=metadata,
            )
            logger.info(f"Created dataset: {name}")
            return dataset.id
        except Exception as e:
            raise LangfuseError(f"Failed to create dataset: {e}")

    async def get_dataset(self, name: str) -> dict[str, Any] | None:
        """
        Get dataset by name.

        Args:
            name: Dataset name

        Returns:
            Dataset info or None if not found
        """
        try:
            client = self._get_client()
            dataset = client.get_dataset(name)
            return {
                "id": dataset.id,
                "name": dataset.name,
                "description": dataset.description,
                "metadata": dataset.metadata,
            }
        except Exception:
            return None

    async def create_dataset_item(
        self,
        dataset_name: str,
        input_data: dict[str, Any],
        expected_output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create dataset item.

        Args:
            dataset_name: Dataset name
            input_data: Input data {"input": "...", "context_files": [...]}
            expected_output: Expected output {"skill": "...", "contains": [...]}
            metadata: Metadata {"case_id": "...", "tags": [...]}

        Returns:
            item_id: Dataset Item ID
        """
        try:
            client = self._get_client()
            item = client.create_dataset_item(
                dataset_name=dataset_name,
                input=input_data,
                expected_output=expected_output,
                metadata=metadata,
            )
            return item.id
        except Exception as e:
            raise LangfuseError(f"Failed to create dataset item: {e}")

    async def update_dataset(
        self,
        dataset_name: str,
        items: list[dict[str, Any]],
    ) -> None:
        """
        Incrementally update dataset.

        Args:
            dataset_name: Dataset name
            items: Items to add or update
        """
        for item in items:
            await self.create_dataset_item(
                dataset_name=dataset_name,
                input_data=item.get("input_data", {}),
                expected_output=item.get("expected_output"),
                metadata=item.get("metadata"),
            )

    # Trace Operations (Read)

    async def get_traces(
        self,
        session_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Trace]:
        """
        Get traces.

        Args:
            session_id: Session ID filter
            limit: Return limit
            offset: Pagination offset

        Returns:
            traces: List of traces
        """
        try:
            client = self._get_client()
            # Use the API to fetch traces
            params: dict[str, Any] = {
                "limit": limit,
                "offset": offset,
            }
            if session_id:
                params["session_id"] = session_id

            response = client.fetch_traces(**params)

            traces = []
            for t in response.data:
                traces.append(
                    Trace(
                        id=t.id,
                        session_id=t.session_id,
                        name=t.name,
                        input=t.input if hasattr(t, "input") else None,
                        output=t.output if hasattr(t, "output") else None,
                        metadata=t.metadata if hasattr(t, "metadata") else None,
                        timestamp=t.timestamp if hasattr(t, "timestamp") else datetime.now(),
                    )
                )
            return traces
        except Exception as e:
            raise LangfuseError(f"Failed to get traces: {e}")

    async def get_trace_detail(self, trace_id: str) -> TraceDetail:
        """
        Get trace detail with spans and generations.

        Args:
            trace_id: Trace ID

        Returns:
            detail: Complete trace information
        """
        try:
            client = self._get_client()
            trace_data = client.fetch_trace(trace_id)

            trace = Trace(
                id=trace_data.id,
                session_id=trace_data.session_id,
                name=trace_data.name,
                input=trace_data.input,
                output=trace_data.output,
                metadata=trace_data.metadata,
            )

            spans = []
            if hasattr(trace_data, "observations"):
                for obs in trace_data.observations:
                    if obs.type == "SPAN":
                        spans.append(
                            Span(
                                id=obs.id,
                                name=obs.name or "",
                                start_time=obs.start_time or datetime.now(),
                                end_time=obs.end_time or datetime.now(),
                                input=obs.input,
                                output=obs.output,
                            )
                        )

            generations = []
            if hasattr(trace_data, "observations"):
                for obs in trace_data.observations:
                    if obs.type == "GENERATION":
                        generations.append(
                            Generation(
                                id=obs.id,
                                model=obs.model or "",
                                prompt=obs.input.get("prompt") if obs.input else None,
                                completion=obs.output.get("completion") if obs.output else None,
                                usage=obs.usage if hasattr(obs, "usage") else None,
                            )
                        )

            return TraceDetail(
                trace=trace,
                spans=spans,
                generations=generations,
            )
        except Exception as e:
            raise LangfuseError(f"Failed to get trace detail: {e}")

    # Score Operations (Write)

    async def add_score(
        self,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:
        """
        Add score to trace.

        Args:
            trace_id: Trace ID
            name: Score dimension (correctness, skill_trigger, etc.)
            value: Score [0, 1]
            comment: Score comment
        """
        try:
            client = self._get_client()
            client.score(
                trace_id=trace_id,
                name=name,
                value=value,
                comment=comment,
            )
            logger.debug(f"Added score {name}={value} to trace {trace_id}")
        except Exception as e:
            raise LangfuseError(f"Failed to add score: {e}")

    async def add_scores_batch(self, scores: list[ScoreInput]) -> None:
        """
        Batch add scores.

        Args:
            scores: List of score inputs
        """
        for score in scores:
            await self.add_score(
                trace_id=score.trace_id,
                name=score.name,
                value=score.value,
                comment=score.comment,
            )

    def flush(self) -> None:
        """Flush pending operations."""
        if self._client:
            self._client.flush()

    def shutdown(self) -> None:
        """Shutdown client."""
        if self._client:
            self._client.shutdown()
            self._client = None
