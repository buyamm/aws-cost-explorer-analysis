# Data Model: 002-detection-rules

## Settings additions
| Field | Default |
|-------|---------|
| `detect_drops` | `True` |
| `drop_ratio` | `0.1` |
| `drop_min_median` | `10.0` |
| `service_overrides` | `{}` — `{service: {key: value}}` |
| `ignore` | `frozenset()` |
| `known` | `frozenset()` |

`for_service(name)` → `Settings` with that service's overrides applied.

## Anomaly additions
| Field | Default |
|-------|---------|
| `kind` | adds `DROP` |
| `month_impact` | `0.0` (always set by `detect`) |
| `known` | `False` |
