from collections.abc import Mapping
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Settings:
    # Detection thresholds
    k: float = 3.5  # robust z-score threshold
    min_delta: float = 10.0  # USD above baseline median
    new_threshold: float = 10.0  # USD/day for services without enough history
    min_history: int = 7  # non-zero baseline days required to use MAD
    driver_tolerance: float = 0.25  # amortized delta within ±25% of usage delta → usage-driven

    # Drops (service falls to near zero)
    detect_drops: bool = True
    drop_ratio: float = 0.1  # cost ≤ 10% of median
    drop_min_median: float = 10.0  # USD/day; cheaper services are not worth a drop alert

    # Windows (days)
    lookback_days: int = 90
    exclude_recent_days: int = 2  # not settled yet in Cost Explorer
    include_provisional: bool = True  # still evaluate those days, marked provisional
    eval_days: int = 7
    baseline_days: int = 30

    # Cost Explorer charges per request; cap pagination
    max_pages: int = 20

    # From the config file
    service_overrides: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    ignore: frozenset[str] = frozenset()
    known: frozenset[str] = frozenset()

    def for_service(self, service: str) -> "Settings":
        """Thresholds that apply to one service (its config overrides on top of these settings)."""
        overrides = self.service_overrides.get(service)
        return replace(self, **overrides) if overrides else self
