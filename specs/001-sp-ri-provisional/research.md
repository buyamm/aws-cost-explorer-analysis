# Research: 001-sp-ri-provisional

## R1. What the usage measure (UnblendedCost) shows for covered usage

- **Finding**: `SavingsPlanCoveredUsage` rows carry the On-Demand-equivalent unblended cost (offset
  by a separate `SavingsPlanNegation` row, which we do not fetch). `DiscountedUsage` (RI-covered)
  rows have unblended rate 0, so unblended cost 0; the RI charge sits in `RIFee`. Sources: AWS
  Data Exports "Line item details" and "Understanding Savings Plans" pages.
- **Decision**: usage measure = `UnblendedCost` over `{Usage, SavingsPlanCoveredUsage,
  DiscountedUsage}`. Amortized measure = `NetAmortizedCost` over the same record types (the
  effective SP/RI cost attributed to the usage). Unused-commitment fees stay out of scope.
- **Alternatives**: `NetAmortizedCost` only (loses usage signal; SP expiry looks like a usage
  spike); `UsageQuantity` (mixed units summed per service, unreliable); separate requests per
  metric (doubles cost, violates constitution IV).

## R2. Driver rule

- **Decision**: `driver = usage` iff `ΔU > 0`, `ΔA > 0` and `|ΔA/ΔU − 1| ≤ driver_tolerance`
  (default 0.25), where Δ = cost − baseline median of each measure on that day. Otherwise `rate`.
  `NEW_SERVICE` rows are always `usage` (new consumption by definition).
- **Why absolute deltas, not ratios**: extra on-demand consumption adds the same dollars to both
  measures (ratio of deltas ≈ 1), even for RI-covered services whose usage measure baseline is 0
  (a ratio-to-baseline would be infinite there).

| Case | ΔU | ΔA | Label |
|------|----|----|-------|
| More uncovered consumption | +X | +X | usage |
| SP expiry, flat usage | ≈0 | +d·X | rate (amortized-only spike) |
| RI expiry, flat usage | +X | +(X − RI cost) | rate |
| Growth absorbed by spare SP | +X | +(1−d)·X | rate (documented limitation) |

## R3. "History" for new-service detection

- **Decision**: count a baseline day as having cost when *either* measure is > 0 (`presence`).
  A fully RI-covered service (usage measure 0, amortized > 0) is therefore not a new service; its
  RI expiry becomes a usage-measure SPIKE labelled `rate`.

## R4. Provisional days and Cost Explorer's `Estimated` flag

- **Finding**: API docs only say `Estimated` "determines whether the result is estimated"; no
  documented boundary. It is commonly true for the whole open month.
- **Decision**: provisional = the `exclude_recent_days` (2) most recent days of the fetch window,
  by recency only. `Estimated` is ignored.
- **Window**: settled days unchanged (`--eval-days`, ending T−3); provisional days T−2, T−1
  appended when `include_provisional` (default True). `MAX_EVAL_DAYS` stays 58 (provisional days'
  baselines lie later, so always inside the lookback).

## R5. Dual detection and de-duplication

- **Decision**: per service/day compute `(su, sa) = score_pair(...)`. If `classify(su)` flags,
  emit one row from `su` (`metric = usage`). Else if `classify(sa) == SPIKE`, emit one row from
  `sa` (`metric = amortized`). Amortized never yields `NEW_SERVICE`.

## R6. Pipeline extraction

- **Decision**: `pipeline.run(session, settings, today) -> RunResult(windows, usage, amortized,
  anomalies)`; it installs the guard on the CE client, fetches, transforms and detects. Errors
  propagate; the CLI keeps mapping them to exit code 2.
