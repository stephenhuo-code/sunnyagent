"""
Trigger factory functions for APScheduler.

Creates DateTrigger and CronTrigger instances from schedule configuration.
"""

from datetime import datetime
from typing import Union, Optional

from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger

from backend.scheduled_tasks.models import (
    ScheduleType,
    OnceScheduleConfig,
    DailyScheduleConfig,
    WeeklyScheduleConfig,
    MonthlyScheduleConfig,
)


def create_trigger(
    schedule_type: ScheduleType,
    schedule_config: dict,
    expiry_date: Optional[datetime] = None,
) -> Union[DateTrigger, CronTrigger]:
    """
    Create an APScheduler trigger from schedule configuration.

    Args:
        schedule_type: The type of schedule (once, daily, weekly, monthly)
        schedule_config: The schedule configuration dictionary
        expiry_date: Optional expiry date for the trigger

    Returns:
        APScheduler trigger instance

    Raises:
        ValueError: If schedule_type or config is invalid
    """
    if schedule_type == ScheduleType.ONCE:
        return create_once_trigger(schedule_config)
    elif schedule_type == ScheduleType.DAILY:
        return create_daily_trigger(schedule_config, expiry_date)
    elif schedule_type == ScheduleType.WEEKLY:
        return create_weekly_trigger(schedule_config, expiry_date)
    elif schedule_type == ScheduleType.MONTHLY:
        return create_monthly_trigger(schedule_config, expiry_date)
    else:
        raise ValueError(f"Unknown schedule type: {schedule_type}")


def create_once_trigger(config: dict) -> DateTrigger:
    """
    Create a DateTrigger for one-time execution.

    Args:
        config: OnceScheduleConfig as dict with run_date and run_time

    Returns:
        DateTrigger instance
    """
    validated = OnceScheduleConfig(**config)

    # Parse date and time
    run_datetime = datetime.strptime(
        f"{validated.run_date} {validated.run_time}",
        "%Y-%m-%d %H:%M"
    )

    return DateTrigger(run_date=run_datetime)


def create_daily_trigger(
    config: dict,
    end_date: Optional[datetime] = None
) -> CronTrigger:
    """
    Create a CronTrigger for daily execution.

    Args:
        config: DailyScheduleConfig as dict with time
        end_date: Optional end date for the trigger

    Returns:
        CronTrigger instance
    """
    validated = DailyScheduleConfig(**config)

    # Parse time
    hour, minute = map(int, validated.time.split(":"))

    return CronTrigger(
        hour=hour,
        minute=minute,
        end_date=end_date,
    )


def create_weekly_trigger(
    config: dict,
    end_date: Optional[datetime] = None
) -> CronTrigger:
    """
    Create a CronTrigger for weekly execution.

    Args:
        config: WeeklyScheduleConfig as dict with days_of_week and time
        end_date: Optional end date for the trigger

    Returns:
        CronTrigger instance
    """
    validated = WeeklyScheduleConfig(**config)

    # Parse time
    hour, minute = map(int, validated.time.split(":"))

    # Convert days list to comma-separated string
    days_str = ",".join(day.value for day in validated.days_of_week)

    return CronTrigger(
        day_of_week=days_str,
        hour=hour,
        minute=minute,
        end_date=end_date,
    )


def create_monthly_trigger(
    config: dict,
    end_date: Optional[datetime] = None
) -> CronTrigger:
    """
    Create a CronTrigger for monthly execution.

    Handles special case where day 31 is selected but month has fewer days
    by using APScheduler's built-in handling.

    Args:
        config: MonthlyScheduleConfig as dict with days_of_month and time
        end_date: Optional end date for the trigger

    Returns:
        CronTrigger instance
    """
    validated = MonthlyScheduleConfig(**config)

    # Parse time
    hour, minute = map(int, validated.time.split(":"))

    # Convert days list to comma-separated string
    # Handle special case: if 31 is in the list, APScheduler will
    # automatically skip months without 31 days
    days_str = ",".join(str(day) for day in sorted(validated.days_of_month))

    return CronTrigger(
        day=days_str,
        hour=hour,
        minute=minute,
        end_date=end_date,
    )


def format_schedule_display(schedule_type: ScheduleType, schedule_config: dict) -> str:
    """
    Format schedule configuration for display.

    Args:
        schedule_type: The type of schedule
        schedule_config: The schedule configuration dictionary

    Returns:
        Human-readable schedule description
    """
    if schedule_type == ScheduleType.ONCE:
        config = OnceScheduleConfig(**schedule_config)
        return f"{config.run_date} {config.run_time}"

    elif schedule_type == ScheduleType.DAILY:
        config = DailyScheduleConfig(**schedule_config)
        return f"每天 {config.time}"

    elif schedule_type == ScheduleType.WEEKLY:
        config = WeeklyScheduleConfig(**schedule_config)
        day_names = {
            "mon": "周一",
            "tue": "周二",
            "wed": "周三",
            "thu": "周四",
            "fri": "周五",
            "sat": "周六",
            "sun": "周日",
        }
        days = ", ".join(day_names.get(d.value, d.value) for d in config.days_of_week)
        return f"每周 {days} {config.time}"

    elif schedule_type == ScheduleType.MONTHLY:
        config = MonthlyScheduleConfig(**schedule_config)
        days = ", ".join(str(d) for d in sorted(config.days_of_month))
        return f"每月 {days}号 {config.time}"

    return "未知计划"
