# Contract: CLI and CSV (001)

## New flag

| Flag | Effect |
|------|--------|
| `--no-provisional` | Do not evaluate the 2 most recent days (pre-001 window) |

`--eval-days N` keeps meaning "N settled days" (1–58). Exit codes unchanged (0 ok, 2 auth/fetch error).

## Cost Explorer request (one per page)

```json
{
  "TimePeriod": {"Start": "<fetch_start>", "End": "<fetch_end>"},
  "Granularity": "DAILY",
  "Metrics": ["UnblendedCost", "NetAmortizedCost"],
  "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
  "Filter": {"Dimensions": {"Key": "RECORD_TYPE",
             "Values": ["Usage", "SavingsPlanCoveredUsage", "DiscountedUsage"]}}
}
```

## CSV columns

`date, service, kind, cost, baseline_median, mad, robust_z, delta, metric, driver, provisional`

- First eight columns unchanged in name and order.
- `metric`: `usage` | `amortized` — which measure the figures come from.
- `driver`: `usage` | `rate`.
- `provisional`: `true` | `false`.
