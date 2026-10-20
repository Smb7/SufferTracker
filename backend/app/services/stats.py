from datetime import datetime, timedelta


def week_start(now: datetime) -> datetime:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start - timedelta(days=now.weekday())
