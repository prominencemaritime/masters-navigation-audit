#!/usr/bin/env python3
"""
Healthcheck script for Docker containers with flexible scheduling.
Supports both SCHEDULE_FREQUENCY_HOURS and SCHEDULE_TIMES modes.

This script checks if /app/logs/health_status.txt exists, contains "OK",
and has been updated recently enough based on the schedule configuration.

Environment Variables:
    SCHEDULE_FREQUENCY_HOURS: Run every N hours (e.g., "2" for every 2 hours)
    SCHEDULE_TIMES: Run at specific times (e.g., "12:00,18:00")
    
At least one must be set. If both are set, SCHEDULE_FREQUENCY_HOURS takes precedence.

Exit Codes:
    0: Healthy
    1: Unhealthy
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


def main():
    """Main healthcheck logic."""
    health_file = Path("/app/logs/health_status.txt")
    
    # Check if health file exists
    if not health_file.exists():
        print("Health status file not found", file=sys.stderr)
        sys.exit(1)
    
    # Read health status
    try:
        content = health_file.read_text().strip()
        if not content.startswith("OK"):
            print(f"Health status is not OK: {content}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Cannot read health status: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Calculate maximum age based on schedule mode
    max_age_minutes = calculate_max_age()
    
    # Check file modification time
    file_age_seconds = datetime.now().timestamp() - health_file.stat().st_mtime
    file_age_minutes = file_age_seconds / 60
    
    if file_age_minutes > max_age_minutes:
        print(
            f"Health status file is too old: {file_age_minutes:.1f} minutes "
            f"(max: {max_age_minutes:.1f} minutes)",
            file=sys.stderr
        )
        sys.exit(1)
    
    # All checks passed
    print(f"Healthy (file age: {file_age_minutes:.1f}/{max_age_minutes:.1f} minutes)")
    sys.exit(0)


def calculate_max_age() -> float:
    """
    Calculate maximum allowed age for health_status.txt based on schedule mode.
    
    Returns:
        Maximum age in minutes
    """
    freq_hours = os.getenv('SCHEDULE_FREQUENCY_HOURS', '').strip()
    schedule_times = os.getenv('SCHEDULE_TIMES', '').strip()
    
    # Mode 1: Frequency-based (e.g., every 2 hours)
    if freq_hours:
        try:
            hours = float(freq_hours)
            # Allow schedule interval + 10 minute buffer
            return hours * 60 + 10
        except (ValueError, TypeError):
            print(f"Invalid SCHEDULE_FREQUENCY_HOURS: {freq_hours}", file=sys.stderr)
            return 70  # Default fallback: 1 hour + 10 min buffer
    
    # Mode 2: Specific times (e.g., 12:00,18:00)
    elif schedule_times:
        try:
            return calculate_max_age_from_times(schedule_times)
        except Exception as e:
            print(f"Error calculating age from SCHEDULE_TIMES: {e}", file=sys.stderr)
            return 70  # Default fallback
    
    # Mode 3: No schedule defined (default to hourly + buffer)
    else:
        print("Warning: Neither SCHEDULE_FREQUENCY_HOURS nor SCHEDULE_TIMES set", file=sys.stderr)
        return 70  # 1 hour + 10 minute buffer


def calculate_max_age_from_times(schedule_times: str) -> float:
    """
    Calculate maximum age based on SCHEDULE_TIMES.
    
    For times like "12:00,18:00", the health file should be updated within
    10 minutes after the most recent scheduled time.
    
    Args:
        schedule_times: Comma-separated list of times (HH:MM format)
    
    Returns:
        Maximum age in minutes
    """
    now = datetime.now()
    
    # Parse all scheduled times
    time_list = [t.strip() for t in schedule_times.split(',')]
    scheduled_datetimes = []
    
    for time_str in time_list:
        try:
            hour, minute = map(int, time_str.split(':'))
            
            # Create datetime for today
            scheduled_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            scheduled_datetimes.append(scheduled_today)
            
            # Also consider yesterday's schedule
            scheduled_yesterday = scheduled_today - timedelta(days=1)
            scheduled_datetimes.append(scheduled_yesterday)
            
        except (ValueError, IndexError) as e:
            print(f"Invalid time format '{time_str}': {e}", file=sys.stderr)
            continue
    
    if not scheduled_datetimes:
        print("No valid times found in SCHEDULE_TIMES", file=sys.stderr)
        return 70
    
    # Find the most recent scheduled time that has passed
    past_times = [dt for dt in scheduled_datetimes if dt <= now]
    
    if not past_times:
        # No scheduled time has passed yet today - use most recent from yesterday
        past_times = sorted(scheduled_datetimes)
    
    most_recent = max(past_times)
    
    # Calculate minutes since most recent scheduled time
    minutes_since = (now - most_recent).total_seconds() / 60
    
    # Allow the time since last schedule + 10 minute buffer
    return minutes_since + 10


if __name__ == "__main__":
    main()
