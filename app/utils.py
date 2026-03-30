"""Utility helpers for date/week calculations and formatting."""
from datetime import datetime, timedelta


def current_week_ending() -> str:
    """Return the ISO date string of the upcoming Sunday (week ending)."""
    today = datetime.utcnow().date()
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0 and datetime.utcnow().hour < 12:
        # If it's Sunday morning, use today
        sunday = today
    else:
        sunday = today + timedelta(days=days_until_sunday)
    return sunday.isoformat()


def previous_week_ending() -> str:
    """Return the ISO date of last Sunday."""
    today = datetime.utcnow().date()
    days_since_sunday = (today.weekday() + 1) % 7
    last_sunday = today - timedelta(days=days_since_sunday)
    return last_sunday.isoformat()


def fmt_money(amount: float) -> str:
    """Format a number as dollars with 2 decimal places."""
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"


def now_iso() -> str:
    """Current UTC datetime as ISO string."""
    return datetime.utcnow().isoformat()
