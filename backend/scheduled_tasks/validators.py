"""
Validators for scheduled task configuration.
"""

from datetime import datetime, date
from typing import Dict, Any, List

from backend.scheduled_tasks.models import (
    ScheduleType,
    OnceScheduleConfig,
    DailyScheduleConfig,
    WeeklyScheduleConfig,
    MonthlyScheduleConfig,
    DayOfWeek,
)


class ValidationError(Exception):
    """Validation error with details."""

    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(message)


def validate_schedule_config(schedule_type: ScheduleType, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate schedule configuration based on schedule type.

    Args:
        schedule_type: The type of schedule
        config: The configuration dictionary

    Returns:
        Validated and normalized configuration

    Raises:
        ValidationError: If configuration is invalid
    """
    if schedule_type == ScheduleType.ONCE:
        return _validate_once_config(config)
    elif schedule_type == ScheduleType.DAILY:
        return _validate_daily_config(config)
    elif schedule_type == ScheduleType.WEEKLY:
        return _validate_weekly_config(config)
    elif schedule_type == ScheduleType.MONTHLY:
        return _validate_monthly_config(config)
    else:
        raise ValidationError(f"Unknown schedule type: {schedule_type}", "schedule_type")


def _validate_once_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate one-time schedule configuration."""
    # Check required fields
    if "run_date" not in config:
        raise ValidationError("run_date is required for once schedule", "schedule_config.run_date")
    if "run_time" not in config:
        raise ValidationError("run_time is required for once schedule", "schedule_config.run_time")

    # Validate date format
    try:
        run_date = datetime.strptime(config["run_date"], "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(
            "run_date must be in YYYY-MM-DD format",
            "schedule_config.run_date"
        )

    # Validate time format
    try:
        _validate_time_format(config["run_time"])
    except ValueError as e:
        raise ValidationError(str(e), "schedule_config.run_time")

    # Validate date is in the future
    run_datetime = datetime.strptime(
        f"{config['run_date']} {config['run_time']}",
        "%Y-%m-%d %H:%M"
    )
    if run_datetime <= datetime.now():
        raise ValidationError(
            "run_date and run_time must be in the future",
            "schedule_config.run_date"
        )

    # Validate using Pydantic model
    validated = OnceScheduleConfig(**config)
    return validated.model_dump()


def _validate_daily_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate daily schedule configuration."""
    # Check required fields
    if "time" not in config:
        raise ValidationError("time is required for daily schedule", "schedule_config.time")

    # Validate time format
    try:
        _validate_time_format(config["time"])
    except ValueError as e:
        raise ValidationError(str(e), "schedule_config.time")

    # Validate using Pydantic model
    validated = DailyScheduleConfig(**config)
    return validated.model_dump()


def _validate_weekly_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate weekly schedule configuration."""
    # Check required fields
    if "days_of_week" not in config:
        raise ValidationError(
            "days_of_week is required for weekly schedule",
            "schedule_config.days_of_week"
        )
    if "time" not in config:
        raise ValidationError("time is required for weekly schedule", "schedule_config.time")

    # Validate days_of_week
    days = config["days_of_week"]
    if not isinstance(days, list) or len(days) == 0:
        raise ValidationError(
            "days_of_week must be a non-empty array",
            "schedule_config.days_of_week"
        )

    valid_days = {d.value for d in DayOfWeek}
    for day in days:
        if day not in valid_days:
            raise ValidationError(
                f"Invalid day of week: {day}. Must be one of: {', '.join(valid_days)}",
                "schedule_config.days_of_week"
            )

    # Validate time format
    try:
        _validate_time_format(config["time"])
    except ValueError as e:
        raise ValidationError(str(e), "schedule_config.time")

    # Validate using Pydantic model
    validated = WeeklyScheduleConfig(**config)
    return validated.model_dump()


def _validate_monthly_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate monthly schedule configuration."""
    # Check required fields
    if "days_of_month" not in config:
        raise ValidationError(
            "days_of_month is required for monthly schedule",
            "schedule_config.days_of_month"
        )
    if "time" not in config:
        raise ValidationError("time is required for monthly schedule", "schedule_config.time")

    # Validate days_of_month
    days = config["days_of_month"]
    if not isinstance(days, list) or len(days) == 0:
        raise ValidationError(
            "days_of_month must be a non-empty array",
            "schedule_config.days_of_month"
        )

    for day in days:
        if not isinstance(day, int) or day < 1 or day > 31:
            raise ValidationError(
                f"Invalid day of month: {day}. Must be between 1 and 31",
                "schedule_config.days_of_month"
            )

    # Validate time format
    try:
        _validate_time_format(config["time"])
    except ValueError as e:
        raise ValidationError(str(e), "schedule_config.time")

    # Validate using Pydantic model
    validated = MonthlyScheduleConfig(**config)
    return validated.model_dump()


def _validate_time_format(time_str: str) -> None:
    """
    Validate time format (HH:MM).

    Raises:
        ValueError: If time format is invalid
    """
    if not isinstance(time_str, str):
        raise ValueError("time must be a string")

    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError("time must be in HH:MM format")

    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        raise ValueError("time must be in HH:MM format with numeric values")

    if hour < 0 or hour > 23:
        raise ValueError("hour must be between 0 and 23")
    if minute < 0 or minute > 59:
        raise ValueError("minute must be between 0 and 59")


def validate_expiry_date(expiry_date: datetime) -> datetime:
    """
    Validate expiry date is in the future.

    Args:
        expiry_date: The expiry date to validate

    Returns:
        The validated expiry date

    Raises:
        ValidationError: If expiry date is not in the future
    """
    if expiry_date <= datetime.now():
        raise ValidationError(
            "expiry_date must be in the future",
            "expiry_date"
        )
    return expiry_date


def validate_script_content(content: str) -> str:
    """
    Validate script content.

    Args:
        content: The script content to validate

    Returns:
        The validated content

    Raises:
        ValidationError: If content is invalid
    """
    if not content or not content.strip():
        raise ValidationError("script_content cannot be empty", "script_content")

    content_bytes = content.encode("utf-8")
    if len(content_bytes) > 65536:  # 64KB
        raise ValidationError(
            "script_content exceeds maximum size of 64KB",
            "script_content"
        )

    return content
