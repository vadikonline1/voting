"""Dates of the vote are days, not hours, in the time zone of the APC (Europe/Chisinau).

- The start of the Adunarea (start_date_vot) is the beginning of the chosen day.
- The deadline (end_date_vot) is the end of the chosen day: the vote is open until 23:59:59 local time.
- Everything is stored as naive UTC datetimes (as before); dates are shown again in local time.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/Chisinau")


def _day(value) -> date | None:
    """The calendar day the admin chose. A date-only value is used as it is; a datetime keeps only its date."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    return date.fromisoformat(text)


def _to_utc_naive(local: datetime) -> datetime:
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def start_of_day(value) -> datetime | None:
    day = _day(value)
    if day is None:
        return None
    return _to_utc_naive(datetime.combine(day, time(0, 0), LOCAL_TZ))


def end_of_day(value) -> datetime | None:
    day = _day(value)
    if day is None:
        return None
    return _to_utc_naive(datetime.combine(day, time(23, 59, 59), LOCAL_TZ))


def local_day(dt: datetime | None) -> date | None:
    """The calendar day in Chisinau of a stored (naive UTC or aware) datetime."""
    if dt is None:
        return None
    aware = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return aware.astimezone(LOCAL_TZ).date()


def today_local() -> date:
    return datetime.now(LOCAL_TZ).date()


def format_day(dt: datetime | None, long: bool = False) -> str | None:
    """dd.mm.yyyy, or "31 octombrie 2026" when long, in Chisinau time."""
    day = local_day(dt)
    if day is None:
        return None
    if not long:
        return day.strftime("%d.%m.%Y")
    months = [
        "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
        "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie",
    ]
    return f"{day.day} {months[day.month - 1]} {day.year}"


def add_days_from(end: datetime, days: int) -> datetime:
    """The end of the day `days` days after the chosen day (calendar days in Chisinau)."""
    return end_of_day(local_day(end) + timedelta(days=days))
