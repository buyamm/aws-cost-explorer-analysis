# Contract: config file, CLI and CSV (002)

## `--config cost-anomaly.toml`

```toml
# Top-level keys must come before the first [table] in TOML
ignore = ["Tax"]                     # never analysed
known = ["AWS Support (Business)"]   # reported with known=true, not alerted (003)

# Thresholds for every service (CLI flags still win)
[defaults]
k = 3.5
min_delta = 10

# Per-service overrides; names exactly as Cost Explorer's SERVICE dimension
[services."Amazon Bedrock"]
min_delta = 50
new_threshold = 50

[services."Amazon Relational Database Service"]
min_delta = 5
```

Allowed keys — `[defaults]`: `k, min_delta, new_threshold, min_history, drop_ratio,
drop_min_median, driver_tolerance`; `[services.*]`: same minus `driver_tolerance`.
Numbers > 0; `min_history` positive integer; `drop_ratio` in (0, 1). Anything else → exit 2.

## New flags

| Flag | Effect |
|------|--------|
| `--config PATH` | Load the file above |
| `--no-drop` | Disable DROP detection |

## CSV columns (appended)

`..., metric, driver, provisional, month_impact, known`

- `kind` may now be `DROP` (delta negative).
- `month_impact`: `delta × days left in the month (inclusive)`, 4 decimals.
- `known`: `true` | `false`.
