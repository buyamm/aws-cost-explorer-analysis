# Implementation Plan: Per-service thresholds, drop alerts and month impact

**Branch**: `002-detection-rules` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

## Summary

Add `settings_file.load_config(path, settings)` (stdlib `tomllib`) producing a `Settings` with
`service_overrides`, `ignore`, `known`; `Settings.for_service(name)` returns the effective
thresholds. Detection and analysis call it per service. Add `DROP` (paid measure collapses,
cross-checked with usage), `--no-drop`, and `Anomaly.month_impact` / `Anomaly.known`.

## Technical Context

**Language/Version**: Python ≥ 3.11 (`tomllib` available) · **Dependencies**: none new ·
**Testing**: pytest · **Project Type**: CLI · **Constraints**: config errors exit 2 before auth.

## Constitution Check

| Principle | Status |
|-----------|--------|
| I. Least privilege | PASS: no AWS change |
| II. Test-first | PASS |
| III. No real AWS | PASS |
| IV. API cost | PASS: config validated before auth, no extra requests |
| V. Explainable | PASS: DROP is a threshold rule; per-service settings flow through `for_service` into report |
| VI. Simplicity | PASS: stdlib `tomllib` |

## Design

- `config.Settings` gains `detect_drops=True`, `drop_ratio=0.1`, `drop_min_median=10.0`,
  `service_overrides: Mapping[str, Mapping[str, float]]` (default empty),
  `ignore: frozenset[str]`, `known: frozenset[str]`, and `for_service(name) -> Settings`
  (`dataclasses.replace` with that service's overrides).
- `settings_file.py`: `ConfigError`; `load_config(path, base) -> Settings`. Keys:
  `[defaults]` (any of `OVERRIDABLE`), `[services."<name>"]` (same keys), `ignore`, `known`.
  `OVERRIDABLE = k, min_delta, new_threshold, min_history, drop_ratio, drop_min_median,
  driver_tolerance` (driver_tolerance only in defaults).
- CLI: threshold flags default to `None`; order = `Settings()` → config `[defaults]` → explicit
  flags. `--config`, `--no-drop`. `ConfigError` → stderr + exit 2 before `assume_role_session`.
- `detect.classify` adds DROP (history ≥ min_history, `detect_drops`, median ≥ drop_min_median,
  cost ≤ drop_ratio × median, z < −k). In `detect()`, after usage/amortized spike checks:
  DROP row iff `classify(sa) == DROP` and (`classify(su) == DROP` or `su.baseline_median == 0`);
  figures from `su` unless its median is 0; `driver = usage`. Ignored services skipped;
  `known` set on rows; `month_impact` computed in `_anomaly`.
- `dates.days_left_in_month(day)`.
- Analysis: per-service settings in explain/near_miss/chart; DROP explanation + near miss
  ("giảm mạnh nhưng chưa tới ngưỡng"); excess sums only positive kinds; "đã biết" label;
  month-impact sentence for ongoing rollups; overrides table rows in params.
- HTML: DROP marker (triangle down, `--drop` token), legend entry; MD: label.

## Project Structure

`src/cost_anomaly/{config,settings_file(new),detect,dates,cli,report,analysis,html_report,md_report}.py`,
tests `test_settings_file.py` (new) + existing, `demo/cost-anomaly.toml` (new) + `run_demo.py`.

## Complexity Tracking

None.
