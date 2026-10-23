from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Detection thresholds
    k: float = 3.5  # robust z-score threshold
    min_delta: float = 10.0  # USD above baseline median
    new_threshold: float = 10.0  # USD/day for services without enough history
    min_history: int = 7  # non-zero baseline days required to use MAD
    driver_tolerance: float = 0.25  # amortized delta within ±25% of usage delta → usage-driven

    # Windows (days)
    lookback_days: int = 90
    exclude_recent_days: int = 2  # not settled yet in Cost Explorer
    include_provisional: bool = True  # still evaluate those days, marked provisional
    eval_days: int = 7
    baseline_days: int = 30

    # Cost Explorer charges per request; cap pagination
    max_pages: int = 20
