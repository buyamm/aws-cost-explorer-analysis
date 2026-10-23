# Implementation Plan: Savings Plans/RI-aware data and provisional recent days

**Branch**: `001-sp-ri-provisional` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-sp-ri-provisional/spec.md`

## Summary

Fetch covered usage (`SavingsPlanCoveredUsage`, `DiscountedUsage`) together with `Usage`, and
request `NetAmortizedCost` next to `UnblendedCost` in the same `GetCostAndUsage` call. Build two
cost matrices (usage, amortized), score each service/day on both with the existing robust
z-score, and label every anomaly `driver = usage | rate` by comparing the absolute increases of
the two measures. Extend the evaluation window with the 2 most recent days marked provisional
(`--no-provisional` restores the old window). Extract the fetch → detect pipeline into
`pipeline.run()` so a scheduled runner can reuse it. CSV gains `metric`, `driver`,
`provisional`; reports show Vietnamese labels.

## Technical Context

**Language/Version**: Python ≥ 3.11

**Primary Dependencies**: boto3/botocore (existing); stdlib only otherwise

**Storage**: CSV/HTML/MD files (existing)

**Testing**: pytest + `botocore.stub.Stubber`; `tests/conftest.py::results_from_matrix`

**Target Platform**: CLI on macOS/Linux; later AWS Lambda (python3.12)

**Project Type**: CLI tool (single package `src/cost_anomaly`)

**Performance Goals**: N/A (≤ 200 services × 90 days)

**Constraints**: same number of Cost Explorer requests; only `ce:GetCostAndUsage`

**Scale/Scope**: ~10 modules touched, ~1 new module

## Constitution Check

| Principle | Status |
|-----------|--------|
| I. Two-layer least privilege | PASS: same single operation; session policy and allowlist unchanged |
| II. Test-first | PASS: every task starts with a failing test (tasks.md) |
| III. No real AWS | PASS: Stubber + fixtures; demo stays offline |
| IV. API cost control | PASS: extra metric and record types ride on the same request; `max_pages` unchanged |
| V. Explainable detection | PASS: driver rule is a plain comparison of two deltas; report re-scores via `detect.score_pair` |
| VI. Simplicity | PASS: no new dependency |

Post-design re-check: PASS (no violations; Complexity Tracking empty).

## Project Structure

### Documentation (this feature)

```text
specs/001-sp-ri-provisional/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/cli.md
└── tasks.md
```

### Source Code (repository root)

```text
src/cost_anomaly/
├── config.py        # + include_provisional, driver_tolerance
├── dates.py         # Windows.provisional_days; window extends to T−1
├── fetch.py         # METRICS, RECORD_TYPES in build_request
├── transform.py     # to_matrix(..., metric=)
├── detect.py        # score(presence=), score_pair, driver(); Anomaly.metric/driver/provisional
├── pipeline.py      # NEW: run(session, settings, today) -> RunResult
├── cli.py           # --no-provisional; uses pipeline.run
├── report.py        # CSV columns metric, driver, provisional
├── analysis.py      # re-score by metric, labels, provisional insight text
├── html_report.py   # badges "tạm tính", "do giá/coverage"
└── md_report.py     # same labels
tests/  (conftest, fixtures/*.json, test_* for each module, new test_pipeline.py)
demo/run_demo.py     # amortized series, SP-expiry + RI-expiry + provisional scenarios
```

**Structure Decision**: keep the single-package layout; one new module `pipeline.py`.

## Complexity Tracking

None.
