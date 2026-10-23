from dataclasses import dataclass, replace
from datetime import date
from statistics import median

from .config import Settings
from .dates import baseline_days, days_left_in_month
from .transform import CostMatrix

MAD_TO_SIGMA = 1.4826

SPIKE = "SPIKE"
NEW_SERVICE = "NEW_SERVICE"
DROP = "DROP"

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
    known: bool = False  # listed under `known` in the config: reported, not alerted
    month_impact: float = 0.0  # delta × days left in the month: cost if it continues


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
    if (
        settings.detect_drops
        and s.baseline_median >= settings.drop_min_median
        and s.cost <= settings.drop_ratio * s.baseline_median
        and s.robust_z < -settings.k
    ):
        return DROP
    return None


def detect(
    matrix: CostMatrix,
    eval_days: list[date],
    settings: Settings,
    amortized: CostMatrix | None = None,
    provisional: frozenset[date] = frozenset(),
) -> list[Anomaly]:
    """Flag each service/day on the usage measure, else an amortized spike, else a drop in both measures."""
    amortized = matrix if amortized is None else amortized
    anomalies: list[Anomaly] = []
    for service in sorted((matrix.keys() | amortized.keys()) - settings.ignore):
        svc = settings.for_service(service)
        usage_series, amortized_series = matrix.get(service, {}), amortized.get(service, {})
        for day in eval_days:
            su, sa = score_pair(usage_series, amortized_series, day, svc)
            kind = classify(su, svc)
            if kind == NEW_SERVICE:
                anomalies.append(_anomaly(day, service, kind, su, USAGE, USAGE))
            elif kind == SPIKE:
                anomalies.append(_anomaly(day, service, kind, su, USAGE, driver(su, sa, svc.driver_tolerance)))
            elif (paid_kind := classify(sa, svc)) == SPIKE:
                anomalies.append(_anomaly(day, service, SPIKE, sa, AMORTIZED, driver(su, sa, svc.driver_tolerance)))
            elif paid_kind == DROP and (kind == DROP or su.baseline_median == 0):
                # What is paid collapsed and usage agrees, so it's not a commitment purchase.
                # Fully RI-covered usage reads $0, so only the paid measure can show it.
                s, metric = (sa, AMORTIZED) if su.baseline_median == 0 else (su, USAGE)
                anomalies.append(_anomaly(day, service, DROP, s, metric, USAGE))
    return [
        replace(a, provisional=a.date in provisional, known=a.service in settings.known) for a in anomalies
    ]


def _anomaly(day: date, service: str, kind: str, s: Score, metric: str, drv: str) -> Anomaly:
    z = None if kind == NEW_SERVICE else s.robust_z
    return Anomaly(
        day, service, kind, s.cost, s.baseline_median, s.mad, z, s.delta, metric, drv,
        month_impact=s.delta * days_left_in_month(day),
    )
