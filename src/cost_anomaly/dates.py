from dataclasses import dataclass
from datetime import date, timedelta

from .config import Settings


@dataclass(frozen=True)
class Windows:
    fetch_start: date  # inclusive
    fetch_end: date  # exclusive (Cost Explorer semantics)
    eval_days: list[date]  # oldest first, provisional days included
    provisional_days: list[date]  # most recent days, not settled in Cost Explorer yet


def compute_windows(today: date, settings: Settings) -> Windows:
    """Fetch [today - lookback, today); evaluate `eval_days` settled days, plus the unsettled ones if enabled."""
    fetch_start = today - timedelta(days=settings.lookback_days)
    newest_settled = today - timedelta(days=settings.exclude_recent_days + 1)
    eval_days = [newest_settled - timedelta(days=i) for i in reversed(range(settings.eval_days))]
    provisional = []
    if settings.include_provisional:
        provisional = [today - timedelta(days=i) for i in range(settings.exclude_recent_days, 0, -1)]

    earliest_baseline = eval_days[0] - timedelta(days=settings.baseline_days)
    if earliest_baseline < fetch_start:
        raise ValueError(
            f"lookback_days={settings.lookback_days} too short: baseline needs data from {earliest_baseline}"
        )
    return Windows(
        fetch_start=fetch_start, fetch_end=today, eval_days=eval_days + provisional, provisional_days=provisional
    )


def baseline_days(day: date, n: int) -> list[date]:
    """The n days immediately before `day`, oldest first."""
    return [day - timedelta(days=i) for i in range(n, 0, -1)]


def date_range(start: date, end: date) -> list[date]:
    """Days in [start, end)."""
    return [start + timedelta(days=i) for i in range((end - start).days)]


def days_left_in_month(day: date) -> int:
    """Days from `day` to the end of its month, both included."""
    next_month = date(day.year + day.month // 12, day.month % 12 + 1, 1)
    return (next_month - day).days
