"""
Pydantic models for scheduled tasks.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ScheduleType(str, Enum):
    """Schedule type enum."""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class TaskStatus(str, Enum):
    """Task status enum."""
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    EXPIRED = "expired"
    ERROR = "error"


class ExecutionStatus(str, Enum):
    """Execution status enum."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class DayOfWeek(str, Enum):
    """Day of week enum."""
    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"


# Schedule Config Models
class OnceScheduleConfig(BaseModel):
    """Config for one-time schedule."""
    run_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date in YYYY-MM-DD format")
    run_time: str = Field(..., pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", description="Time in HH:MM format")


class DailyScheduleConfig(BaseModel):
    """Config for daily schedule."""
    time: str = Field(..., pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", description="Time in HH:MM format")


class WeeklyScheduleConfig(BaseModel):
    """Config for weekly schedule."""
    days_of_week: List[DayOfWeek] = Field(..., min_length=1, max_length=7)
    time: str = Field(..., pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", description="Time in HH:MM format")


class MonthlyScheduleConfig(BaseModel):
    """Config for monthly schedule."""
    days_of_month: List[int] = Field(..., min_length=1, max_length=31)
    time: str = Field(..., pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", description="Time in HH:MM format")

    @field_validator("days_of_month")
    @classmethod
    def validate_days(cls, v: List[int]) -> List[int]:
        for day in v:
            if day < 1 or day > 31:
                raise ValueError(f"Day must be between 1 and 31, got {day}")
        return v


ScheduleConfig = Union[OnceScheduleConfig, DailyScheduleConfig, WeeklyScheduleConfig, MonthlyScheduleConfig]


# Database Entity Models
class ScheduledTaskBase(BaseModel):
    """Base model for scheduled task."""
    title: str = Field(..., min_length=1, max_length=255)
    schedule_type: ScheduleType
    schedule_config: dict
    expiry_date: Optional[datetime] = None


class ScheduledTaskCreate(ScheduledTaskBase):
    """Model for creating a scheduled task."""
    script_content: str = Field(..., min_length=1, max_length=65536, description="Prompt/script content (max 64KB)")


class ScheduledTaskUpdate(BaseModel):
    """Model for updating a scheduled task."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    schedule_type: Optional[ScheduleType] = None
    schedule_config: Optional[dict] = None
    script_content: Optional[str] = Field(None, min_length=1, max_length=65536)
    expiry_date: Optional[datetime] = None


class ScheduledTask(ScheduledTaskBase):
    """Full scheduled task model."""
    id: UUID
    user_id: UUID
    enabled: bool = True
    status: TaskStatus = TaskStatus.SCHEDULED
    script_file_path: str
    apscheduler_job_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    next_run_time: Optional[datetime] = None
    last_run_time: Optional[datetime] = None
    last_run_status: Optional[ExecutionStatus] = None

    class Config:
        from_attributes = True


class ScheduledTaskWithScript(ScheduledTask):
    """Scheduled task with script content."""
    script_content: Optional[str] = None


# Task Execution Models
class TaskExecutionBase(BaseModel):
    """Base model for task execution."""
    task_id: UUID
    execution_time: datetime
    status: ExecutionStatus


class TaskExecutionCreate(TaskExecutionBase):
    """Model for creating a task execution record."""
    pass


class TaskExecution(TaskExecutionBase):
    """Full task execution model."""
    id: UUID
    duration_ms: Optional[int] = None
    retry_count: int = 0
    log_file_path: Optional[str] = None
    conversation_id: Optional[UUID] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TaskExecutionDetail(TaskExecution):
    """Task execution with log content."""
    log_content: Optional[str] = None


# List Response Models
class ScheduledTaskList(BaseModel):
    """Paginated list of scheduled tasks."""
    items: List[ScheduledTask]
    total: int
    page: int
    page_size: int


class AdminScheduledTask(ScheduledTask):
    """Scheduled task with user info for admin view."""
    username: Optional[str] = None


class AdminScheduledTaskList(BaseModel):
    """Paginated list of scheduled tasks for admin."""
    items: List[AdminScheduledTask]
    total: int
    page: int
    page_size: int


class TaskExecutionList(BaseModel):
    """Paginated list of task executions."""
    items: List[TaskExecution]
    total: int
    page: int
    page_size: int


# Settings Models
class ScheduledTasksSettings(BaseModel):
    """Global settings for scheduled tasks feature."""
    global_enabled: bool = True
    max_concurrent_tasks: int = 5
    default_timeout_minutes: int = 15


class UpdateScheduledTasksSettingsRequest(BaseModel):
    """Request to update global settings."""
    global_enabled: Optional[bool] = None
    max_concurrent_tasks: Optional[int] = Field(None, ge=1, le=20)
    default_timeout_minutes: Optional[int] = Field(None, ge=1, le=60)
