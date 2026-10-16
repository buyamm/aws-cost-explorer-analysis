from dataclasses import dataclass
from datetime import date
from statistics import median

from .config import Settings
from .dates import baseline_days
from .transform import CostMatrix

MAD_TO_SIGMA = 1.4826

SPIKE = "SPIKE"
NEW_SERVICE = "NEW_SERVICE"


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


def score(series: dict[date, float], day: date, settings: Settings) -> Score:
    cost = series.get(day, 0.0)
    baseline = [series.get(d, 0.0) for d in baseline_days(day, settings.baseline_days)]
    med = median(baseline)
    mad = median(abs(b - med) for b in baseline)
    scale = robust_scale(med, mad)
    delta = cost - med
    history = sum(1 for b in baseline if b > 0)
    return Score(cost, med, mad, history, scale, delta / scale, delta)


def classify(s: Score, settings: Settings) -> str | None:
    if s.history_days < settings.min_history:
        return NEW_SERVICE if s.cost >= settings.new_threshold else None
    if s.robust_z > settings.k and s.delta >= settings.min_delta:
        return SPIKE
    return None


def detect(matrix: CostMatrix, eval_days: list[date], settings: Settings) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    for service, series in sorted(matrix.items()):
        for day in eval_days:
            s = score(series, day, settings)
            kind = classify(s, settings)
            if kind:
                z = s.robust_z if kind == SPIKE else None
                anomalies.append(Anomaly(day, service, kind, s.cost, s.baseline_median, s.mad, z, s.delta))
    return anomalies
