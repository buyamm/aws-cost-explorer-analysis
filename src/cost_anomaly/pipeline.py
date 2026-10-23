"""Fetch → transform → detect for an already-authenticated session (shared by the CLI and scheduled runs)."""

from dataclasses import dataclass
from datetime import date

from botocore.exceptions import BotoCoreError

from .cad import CadAnomaly, fetch_anomalies, match
from .config import Settings
from .dates import Windows, compute_windows
from .detect import Anomaly, detect
from .fetch import CostExplorerError, TooManyPages, fetch_daily_costs
from .guard import ALLOWED_OPERATIONS, CAD_OPERATIONS, ForbiddenOperation, install_guard
from .transform import AMORTIZED_METRIC, USAGE_METRIC, CostMatrix, to_matrix


@dataclass(frozen=True)
class RunResult:
    windows: Windows
    usage: CostMatrix
    amortized: CostMatrix
    anomalies: list[Anomaly]
    cad: list[CadAnomaly] | None = None  # None: not requested or unavailable
    cad_error: str | None = None


def run(session, settings: Settings, today: date, with_cad: bool = False) -> RunResult:
    """Raises the cost fetch errors (CostExplorerError, TooManyPages, BotoCoreError) for the caller to map.

    CAD is a secondary signal: its errors are returned in `cad_error`, never raised.
    """
    windows = compute_windows(today, settings)
    allowed = CAD_OPERATIONS if with_cad else ALLOWED_OPERATIONS
    client = install_guard(session.client("ce", region_name="us-east-1"), allowed)
    results = fetch_daily_costs(client, windows.fetch_start, windows.fetch_end, settings.max_pages)
    usage = to_matrix(results, windows.fetch_start, windows.fetch_end, USAGE_METRIC)
    amortized = to_matrix(results, windows.fetch_start, windows.fetch_end, AMORTIZED_METRIC)
    anomalies = detect(usage, windows.eval_days, settings, amortized, frozenset(windows.provisional_days))
    if not with_cad:
        return RunResult(windows, usage, amortized, anomalies)
    try:
        cad = fetch_anomalies(client, windows.eval_days[0], windows.eval_days[-1], settings.max_pages)
    except (CostExplorerError, TooManyPages, ForbiddenOperation, BotoCoreError) as e:
        return RunResult(windows, usage, amortized, anomalies, cad_error=str(e))
    return RunResult(windows, usage, amortized, match(anomalies, cad, windows.eval_days[-1]), cad)
