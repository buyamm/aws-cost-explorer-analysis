from dataclasses import dataclass, replace
from datetime import date
from statistics import median

from .config import Settings
from .dates import baseline_days
from .transform import CostMatrix

MAD_TO_SIGMA = 1.4826

SPIKE = "SPIKE"
NEW_SERVICE = "NEW_SERVICE"

# Anomaly.metric (which measure the figures come from) and Anomaly.driver
USAGE = "usage"
AMORTIZED = "amortized"
RATE = "rate"


@dataclass(frozen=True)
class Anomaly:
    date: date
    service: str
    kind: str
    cost: float
    baseline_median: float
    mad: float
    robust_z: float | None  # None for NEW_SERVICE
    delta: float
    metric: str = USAGE  # figures above come from the usage or the amortized measure
    driver: str = USAGE  # USAGE or RATE (coverage/price change)
    provisional: bool = False


@dataclass(frozen=True)
class Score:
    """One service on one day, measured against the baseline days before it."""

    cost: float
    baseline_median: float
    mad: float
    history_days: int  # baseline days with non-zero cost
    scale: float
    robust_z: float
    delta: float


def robust_scale(med: float, mad: float) -> float:
    # Fallback keeps flat baselines (MAD == 0) from dividing by zero; min_delta still filters noise.
    return max(MAD_TO_SIGMA * mad, 0.01 * abs(med), 0.01)


def score(
    series: dict[date, float], day: date, settings: Settings, presence: dict[date, float] | None = None
) -> Score:
    """`presence` (default: `series`) decides which baseline days count as history."""
    days = baseline_days(day, settings.baseline_days)
    cost = series.get(day, 0.0)
    baseline = [series.get(d, 0.0) for d in days]
    med = median(baseline)
    mad = median(abs(b - med) for b in baseline)
    scale = robust_scale(med, mad)
    delta = cost - med
    history = sum(1 for d in days if (presence or series).get(d, 0.0) > 0)
    return Score(cost, med, mad, history, scale, delta / scale, delta)


def score_pair(
    usage: dict[date, float], amortized: dict[date, float], day: date, settings: Settings
) -> tuple[Score, Score]:
    """Score both measures; a day has history if either measure had cost (RI-covered usage reads $0)."""
    presence = {d: max(usage.get(d, 0.0), amortized.get(d, 0.0)) for d in usage.keys() | amortized.keys()}
    return score(usage, day, settings, presence), score(amortized, day, settings, presence)


def driver(usage: Score, amortized: Score, tolerance: float) -> str:
    """usage when extra consumption added about the same dollars to both measures, else rate."""
    if usage.delta > 0 and amortized.delta > 0 and abs(amortized.delta / usage.delta - 1) <= tolerance:
        return USAGE
    return RATE


def classify(s: Score, settings: Settings) -> str | None:
    if s.history_days < settings.min_history:
        return NEW_SERVICE if s.cost >= settings.new_threshold else None
    if s.robust_z > settings.k and s.delta >= settings.min_delta:
        return SPIKE
    return None


def detect(
    matrix: CostMatrix,
    eval_days: list[date],
    settings: Settings,
    amortized: CostMatrix | None = None,
    provisional: frozenset[date] = frozenset(),
) -> list[Anomaly]:
    """Flag each service/day on the usage measure, or else on the amortized measure (spikes only)."""
    amortized = matrix if amortized is None else amortized
    anomalies: list[Anomaly] = []
    for service in sorted(matrix.keys() | amortized.keys()):
        usage_series, amortized_series = matrix.get(service, {}), amortized.get(service, {})
        for day in eval_days:
            su, sa = score_pair(usage_series, amortized_series, day, settings)
            kind = classify(su, settings)
            if kind == NEW_SERVICE:
                anomalies.append(_anomaly(day, service, kind, su, USAGE, USAGE))
            elif kind == SPIKE:
                anomalies.append(_anomaly(day, service, kind, su, USAGE, driver(su, sa, settings.driver_tolerance)))
            elif classify(sa, settings) == SPIKE:
                anomalies.append(_anomaly(day, service, SPIKE, sa, AMORTIZED, driver(su, sa, settings.driver_tolerance)))
    return [replace(a, provisional=True) if a.date in provisional else a for a in anomalies]


def _anomaly(day: date, service: str, kind: str, s: Score, metric: str, drv: str) -> Anomaly:
    z = s.robust_z if kind == SPIKE else None
    return Anomaly(day, service, kind, s.cost, s.baseline_median, s.mad, z, s.delta, metric, drv)
