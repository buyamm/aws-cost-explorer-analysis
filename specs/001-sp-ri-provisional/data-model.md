# Data Model: 001-sp-ri-provisional

## Settings (config.py) — additions

| Field | Default | Meaning |
|-------|---------|---------|
| `include_provisional` | `True` | Evaluate the `exclude_recent_days` most recent days, marked provisional |
| `driver_tolerance` | `0.25` | Max relative gap between ΔA and ΔU for `driver = usage` |

## Windows (dates.py)

| Field | Change |
|-------|--------|
| `eval_days` | settled days (count `eval_days`, newest = T−3) + provisional days when enabled; oldest first |
| `provisional_days` | NEW: list of provisional dates (subset of `eval_days`, empty when disabled) |

## Cost matrices (transform.py)

`CostMatrix = {service: {day: amount}}`, one per metric: `usage` (UnblendedCost) and `amortized`
(NetAmortizedCost). A service present in one matrix is zero-filled in the other. Missing metric
in a group → 0.0.

## Score (detect.py)

Unchanged fields; `history_days` counted from a `presence` series (max of both measures) when
given.

## Anomaly (detect.py) — additions (defaults keep old constructors valid)

| Field | Values | Default |
|-------|--------|---------|
| `metric` | `usage` \| `amortized` | `usage` |
| `driver` | `usage` \| `rate` | `usage` |
| `provisional` | bool | `False` |

## RunResult (pipeline.py)

`windows: Windows`, `usage: CostMatrix`, `amortized: CostMatrix`, `anomalies: list[Anomaly]`.
