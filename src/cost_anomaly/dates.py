from dataclasses import dataclass
from datetime import date, timedelta

from .config import Settings


@dataclass(frozen=True)
class Windows:
    fetch_start: date  # inclusive
    fetch_end: date  # exclusive (Cost Explorer semantics)
    eval_days: list[date]  # oldest first


def compute_windows(today: date, settings: Settings) -> Windows:
    """Fetch [today - lookback, today); evaluate the newest days excluding the most recent ones."""
    fetch_start = today - timedelta(days=settings.lookback_days)
    newest_eval = today - timedelta(days=settings.exclude_recent_days + 1)
    eval_days = [newest_eval - timedelta(days=i) for i in reversed(range(settings.eval_days))]

    earliest_baseline = eval_days[0] - timedelta(days=settings.baseline_days)
    if earliest_baseline < fetch_start:
        raise ValueError(
            f"lookback_days={settings.lookback_days} too short: baseline needs data from {earliest_baseline}"
        )
    return Windows(fetch_start=fetch_start, fetch_end=today, eval_days=eval_days)


def baseline_days(day: date, n: int) -> list[date]:
    """The n days immediately before `day`, oldest first."""
    return [day - timedelta(days=i) for i in range(n, 0, -1)]


def date_range(start: date, end: date) -> list[date]:
    """Days in [start, end)."""
    return [start + timedelta(days=i) for i in range((end - start).days)]
