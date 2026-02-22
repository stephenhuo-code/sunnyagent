"""
Intent parser for scheduled task creation from natural language.

Extracts schedule intent from user messages like:
- "每天早上9点执行：分析今日新闻"
- "每周一和周五下午3点提醒我开会"
- "下个月15号发送报告"
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from dataclasses import dataclass

from backend.scheduled_tasks.models import ScheduleType, DayOfWeek

logger = logging.getLogger(__name__)


@dataclass
class ParsedScheduleIntent:
    """Parsed schedule intent from natural language."""
    schedule_type: ScheduleType
    schedule_config: dict
    prompt: str
    title: Optional[str] = None
    expiry_date: Optional[datetime] = None


# Time patterns
TIME_PATTERN = re.compile(
    r"(?:早上|上午|中午|下午|晚上|凌晨)?(?:(\d{1,2})[点时:])?(?:(\d{1,2})分?)?",
    re.IGNORECASE,
)

# Day of week mapping
DAY_OF_WEEK_MAP = {
    "一": DayOfWeek.MON,
    "1": DayOfWeek.MON,
    "二": DayOfWeek.TUE,
    "2": DayOfWeek.TUE,
    "三": DayOfWeek.WED,
    "3": DayOfWeek.WED,
    "四": DayOfWeek.THU,
    "4": DayOfWeek.THU,
    "五": DayOfWeek.FRI,
    "5": DayOfWeek.FRI,
    "六": DayOfWeek.SAT,
    "6": DayOfWeek.SAT,
    "日": DayOfWeek.SUN,
    "天": DayOfWeek.SUN,
    "7": DayOfWeek.SUN,
    "0": DayOfWeek.SUN,
}

# Schedule type keywords
DAILY_KEYWORDS = ["每天", "天天", "每日", "daily"]
WEEKLY_KEYWORDS = ["每周", "每星期", "weekly", "周"]
MONTHLY_KEYWORDS = ["每月", "每个月", "monthly"]
ONCE_KEYWORDS = ["明天", "后天", "下周", "下月", "once"]


def parse_schedule_intent(message: str) -> Optional[ParsedScheduleIntent]:
    """
    Parse a user message for schedule intent.

    Args:
        message: The user message to parse

    Returns:
        ParsedScheduleIntent if schedule intent detected, None otherwise
    """
    # Check for schedule-related keywords
    if not _has_schedule_keywords(message):
        return None

    # Try to parse different schedule types
    result = _try_parse_daily(message)
    if result:
        return result

    result = _try_parse_weekly(message)
    if result:
        return result

    result = _try_parse_monthly(message)
    if result:
        return result

    result = _try_parse_once(message)
    if result:
        return result

    return None


def _has_schedule_keywords(message: str) -> bool:
    """Check if message contains schedule-related keywords."""
    all_keywords = (
        DAILY_KEYWORDS
        + WEEKLY_KEYWORDS
        + MONTHLY_KEYWORDS
        + ONCE_KEYWORDS
        + ["定时", "提醒", "执行", "运行", "scheduled"]
    )
    return any(kw in message.lower() for kw in all_keywords)


def _parse_time(message: str) -> Tuple[int, int]:
    """Parse time from message, returns (hour, minute)."""
    # Default time
    hour, minute = 9, 0

    # Check for period indicators and adjust hour
    if "下午" in message or "晚上" in message:
        hour_offset = 12
    elif "凌晨" in message:
        hour_offset = 0
    else:
        hour_offset = 0

    # Try to find explicit time
    time_match = re.search(r"(\d{1,2})[点时:：](?:(\d{1,2})分?)?", message)
    if time_match:
        hour = int(time_match.group(1))
        if time_match.group(2):
            minute = int(time_match.group(2))
        else:
            minute = 0

        # Apply period offset if hour < 12
        if hour < 12 and hour_offset == 12:
            hour += 12

    # Handle special time words
    if "早上" in message and hour > 12:
        hour -= 12
    if any(word in message for word in ["中午", "午时"]):
        hour = 12

    return hour, minute


def _extract_prompt(message: str) -> str:
    """Extract the actual prompt/task content from the message."""
    # Common separators
    separators = ["：", ":", "执行", "提醒", "运行", "帮我", "请"]

    for sep in separators:
        if sep in message:
            parts = message.split(sep, 1)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip()

    # If no separator found, use the whole message
    return message


def _try_parse_daily(message: str) -> Optional[ParsedScheduleIntent]:
    """Try to parse as daily schedule."""
    if not any(kw in message for kw in DAILY_KEYWORDS):
        return None

    hour, minute = _parse_time(message)
    prompt = _extract_prompt(message)

    return ParsedScheduleIntent(
        schedule_type=ScheduleType.DAILY,
        schedule_config={"time": f"{hour:02d}:{minute:02d}"},
        prompt=prompt,
    )


def _try_parse_weekly(message: str) -> Optional[ParsedScheduleIntent]:
    """Try to parse as weekly schedule."""
    if not any(kw in message for kw in WEEKLY_KEYWORDS):
        return None

    # Extract days of week
    days = []
    for char, day_enum in DAY_OF_WEEK_MAP.items():
        if f"周{char}" in message or f"星期{char}" in message:
            if day_enum not in days:
                days.append(day_enum)

    # Default to Monday if no specific day found
    if not days:
        days = [DayOfWeek.MON]

    hour, minute = _parse_time(message)
    prompt = _extract_prompt(message)

    return ParsedScheduleIntent(
        schedule_type=ScheduleType.WEEKLY,
        schedule_config={
            "days_of_week": [d.value for d in days],
            "time": f"{hour:02d}:{minute:02d}",
        },
        prompt=prompt,
    )


def _try_parse_monthly(message: str) -> Optional[ParsedScheduleIntent]:
    """Try to parse as monthly schedule."""
    if not any(kw in message for kw in MONTHLY_KEYWORDS):
        return None

    # Extract days of month
    days = []
    day_matches = re.findall(r"(\d{1,2})号?日?", message)
    for day_str in day_matches:
        day = int(day_str)
        if 1 <= day <= 31 and day not in days:
            days.append(day)

    # Default to 1st if no specific day found
    if not days:
        days = [1]

    hour, minute = _parse_time(message)
    prompt = _extract_prompt(message)

    return ParsedScheduleIntent(
        schedule_type=ScheduleType.MONTHLY,
        schedule_config={
            "days_of_month": sorted(days),
            "time": f"{hour:02d}:{minute:02d}",
        },
        prompt=prompt,
    )


def _try_parse_once(message: str) -> Optional[ParsedScheduleIntent]:
    """Try to parse as one-time schedule."""
    now = datetime.now()
    run_date = None

    # Check for relative dates
    if "明天" in message:
        run_date = now + timedelta(days=1)
    elif "后天" in message:
        run_date = now + timedelta(days=2)
    elif "大后天" in message:
        run_date = now + timedelta(days=3)

    # Check for next week
    if "下周" in message or "下星期" in message:
        # Find the next occurrence of the specified day
        for char, day_enum in DAY_OF_WEEK_MAP.items():
            if f"下周{char}" in message or f"下星期{char}" in message:
                target_weekday = {
                    DayOfWeek.MON: 0,
                    DayOfWeek.TUE: 1,
                    DayOfWeek.WED: 2,
                    DayOfWeek.THU: 3,
                    DayOfWeek.FRI: 4,
                    DayOfWeek.SAT: 5,
                    DayOfWeek.SUN: 6,
                }[day_enum]
                days_ahead = target_weekday - now.weekday() + 7
                if days_ahead <= 7:
                    days_ahead += 7
                run_date = now + timedelta(days=days_ahead)
                break

        if run_date is None and "下周" in message:
            # Default to next Monday
            days_ahead = 7 - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            run_date = now + timedelta(days=days_ahead)

    # Check for specific date
    date_match = re.search(r"(\d{1,2})月(\d{1,2})号?日?", message)
    if date_match:
        month = int(date_match.group(1))
        day = int(date_match.group(2))
        year = now.year
        if month < now.month or (month == now.month and day < now.day):
            year += 1
        try:
            run_date = datetime(year, month, day)
        except ValueError:
            pass

    if run_date is None:
        return None

    hour, minute = _parse_time(message)
    prompt = _extract_prompt(message)

    return ParsedScheduleIntent(
        schedule_type=ScheduleType.ONCE,
        schedule_config={
            "run_date": run_date.strftime("%Y-%m-%d"),
            "run_time": f"{hour:02d}:{minute:02d}",
        },
        prompt=prompt,
    )


def detect_schedule_intent(message: str) -> bool:
    """
    Quick check if message contains schedule intent.

    This is a lightweight check for use in intent classification.

    Args:
        message: The user message to check

    Returns:
        True if message likely contains schedule intent
    """
    return _has_schedule_keywords(message)
