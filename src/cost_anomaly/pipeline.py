"""Fetch → transform → detect for an already-authenticated session (shared by the CLI and scheduled runs)."""

from dataclasses import dataclass
from datetime import date

from .config import Settings
from .dates import Windows, compute_windows
from .detect import Anomaly, detect
from .fetch import fetch_daily_costs
from .guard import install_guard
from .transform import AMORTIZED_METRIC, USAGE_METRIC, CostMatrix, to_matrix


@dataclass(frozen=True)
class RunResult:
    windows: Windows
    usage: CostMatrix
    amortized: CostMatrix
    anomalies: list[Anomaly]


def run(session, settings: Settings, today: date) -> RunResult:
    """Raises the fetch errors (CostExplorerError, TooManyPages, BotoCoreError) for the caller to map."""
    windows = compute_windows(today, settings)
    client = install_guard(session.client("ce", region_name="us-east-1"))
    results = fetch_daily_costs(client, windows.fetch_start, windows.fetch_end, settings.max_pages)
    usage = to_matrix(results, windows.fetch_start, windows.fetch_end, USAGE_METRIC)
    amortized = to_matrix(results, windows.fetch_start, windows.fetch_end, AMORTIZED_METRIC)
    anomalies = detect(usage, windows.eval_days, settings, amortized, frozenset(windows.provisional_days))
    return RunResult(windows, usage, amortized, anomalies)
