# Tasks: Savings Plans/RI-aware data and provisional recent days

**Input**: Design documents from `specs/001-sp-ri-provisional/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md

**Tests**: REQUIRED (constitution II, test-first). Every implementation task is preceded by a
test task that must be seen failing with `uv run pytest` before the code is written.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Run `uv run pytest -q` on the branch and record the baseline (56 passed)

## Phase 2: Foundational (blocking)

- [X] T002 Extend `tests/conftest.py::results_from_matrix(matrix, amortized=None)` to emit both `UnblendedCost` and `NetAmortizedCost` per group (amortized defaults to the usage amounts); add `NetAmortizedCost` equal to `UnblendedCost` in `tests/fixtures/ce_page1.json`, `ce_page2.json`, `ce_new_service.json`
- [X] T003 Test then implement `Settings.include_provisional = True` and `Settings.driver_tolerance = 0.25` in `src/cost_anomaly/config.py` (test in `tests/test_detect.py` or a small `tests/test_config.py`)

**Checkpoint**: existing suite still green.

## Phase 3: User Story 1 — No fake spikes when SP/RI change (P1) 🎯 MVP

**Goal**: covered usage counted; anomalies carry `metric` and `driver`.
**Independent test**: synthetic SP expiry with flat usage → one amortized SPIKE labelled `rate`, no usage-driven row.

- [X] T004 [P] [US1] Failing test in `tests/test_fetch.py::test_request_shape`: `Metrics == ["UnblendedCost", "NetAmortizedCost"]`, `RECORD_TYPE` values `["Usage", "SavingsPlanCoveredUsage", "DiscountedUsage"]`; then update `build_request` in `src/cost_anomaly/fetch.py` (module constants `METRICS`, `RECORD_TYPES`)
- [X] T005 [P] [US1] Failing tests in `tests/test_transform.py`: `to_matrix(..., metric="NetAmortizedCost")` sums amortized amounts across pages; a group missing the metric counts as 0.0; then add `metric` param (default `"UnblendedCost"`, constants `USAGE_METRIC`, `AMORTIZED_METRIC`) in `src/cost_anomaly/transform.py`
- [X] T006 [US1] Failing tests in `tests/test_detect.py`: `score(series, day, settings, presence=...)` counts history from `presence`; `driver(su, sa, tol)` returns `usage` iff `ΔU > 0`, `ΔA > 0`, `|ΔA/ΔU − 1| ≤ tol`, else `rate` (table in research.md R2); then implement `score(presence=)`, `score_pair(usage_series, amortized_series, day, settings) -> (Score, Score)` and `driver()` in `src/cost_anomaly/detect.py`
- [X] T007 [US1] Failing tests in `tests/test_detect.py` for `detect(matrix, eval_days, settings, amortized=None, provisional=frozenset())`: (a) SP expiry: flat usage, amortized 70→100 → one row `metric="amortized"`, `driver="rate"`, `kind=SPIKE`; (b) usage doubles in both measures → one row `metric="usage"`, `driver="usage"`; (c) RI-covered service (usage 0, amortized 60) whose RI expires (usage 0→95, amortized 60→95) → `SPIKE`, `metric="usage"`, `driver="rate"`, not `NEW_SERVICE`; (d) both measures anomalous → exactly one row; (e) `amortized=None` behaves exactly as before; then add `Anomaly.metric="usage"`, `Anomaly.driver="usage"`, `Anomaly.provisional=False` defaults and implement the dual detection (research.md R5; NEW_SERVICE only from usage, always `driver="usage"`)
- [X] T008 [US1] Failing test in `tests/test_report.py`: header is `date,service,kind,cost,baseline_median,mad,robust_z,delta,metric,driver,provisional` and rows render `metric`, `driver`, `provisional` as `true`/`false`; then update `FIELDS`/`write_csv` in `src/cost_anomaly/report.py`
- [X] T009 [US1] Failing tests in `tests/test_analysis.py`: `build_report(..., amortized=...)` re-scores an amortized row from the amortized matrix (row `score.cost` equals the anomaly cost), explanation of a `rate` row mentions "giá/coverage", COLUMNS documents `metric`/`driver`, params list `driver_tolerance`; then update `src/cost_anomaly/analysis.py` (use `detect.score_pair` everywhere scores are recomputed, incl. near misses and `chart_points`)
- [X] T010 [US1] Failing tests (HTML and MD) that a `rate` row shows the badge "do giá/coverage"; then update `src/cost_anomaly/html_report.py` and `src/cost_anomaly/md_report.py`

**Checkpoint**: US1 done; suite green.

## Phase 4: User Story 2 — Provisional recent days (P2)

**Goal**: T−2, T−1 evaluated and marked provisional; `--no-provisional` restores old window.
**Independent test**: spike on T−1 appears with `provisional=true`.

- [X] T011 [US2] Failing tests in `tests/test_dates.py`: default window = settled 2026-10-06..12 + provisional 10-13, 10-14 (`eval_days` has 9 days, `provisional_days == [10-13, 10-14]`); `include_provisional=False` → old 7 days and empty `provisional_days`; then implement in `src/cost_anomaly/dates.py`
- [X] T012 [US2] Failing test in `tests/test_detect.py`: anomalies on days in `provisional` get `provisional=True`; then implement in `detect()`
- [X] T013 [US2] Failing tests in `tests/test_cli.py`: spike on 2026-10-14 with `--end-date 2026-10-15` is reported with `provisional=true`; `--no-provisional` drops it and leaves other results identical; `test_eval_days_max_fits_lookback` asserts settled-day count 58; then add `--no-provisional` in `src/cost_anomaly/cli.py`
- [X] T014 [US2] Failing tests in `tests/test_analysis.py`: insight text says the provisional days are evaluated with the label "tạm tính" (or, when disabled, keeps the old "không được đánh giá" note); provisional rows get a "tạm tính" badge in HTML/MD; params list `include_provisional` with flag `--no-provisional`; then update `analysis.py`, `html_report.py`, `md_report.py`

**Checkpoint**: US1 + US2 done; suite green.

## Phase 5: User Story 3 — Reusable pipeline (P3)

- [X] T015 [US3] Failing test `tests/test_pipeline.py`: `pipeline.run(session, settings, today)` with a fake session returning a stubbed CE client returns `RunResult(windows, usage, amortized, anomalies)`, installs the guard (a non-allowlisted call on the client raises `ForbiddenOperation`), writes no files and does not prompt; then create `src/cost_anomaly/pipeline.py`
- [X] T016 [US3] Refactor `src/cost_anomaly/cli.py::main` to call `pipeline.run` (auth stays in the CLI; error mapping to exit 2 unchanged); `tests/test_cli.py` must stay green without edits beyond T013

## Phase 6: Polish

- [X] T017 [P] Update `demo/run_demo.py`: emit both metrics; scenarios "AWS Fargate" SP expiry (usage flat 80, amortized 52→80), "Amazon ElastiCache" RI expiry (usage 0→95, amortized 60→95), EC2 Compute partly SP-covered with a usage-driven fleet spike, CloudWatch spike on T−1 (provisional); update SCENARIOS text and the printed table (metric, driver, provisional)
- [X] T018 [P] Update `README.md` (Vietnamese): data now includes SP/RI-covered usage, the two measures, driver labels, provisional days, `--no-provisional`, CSV columns
- [X] T019 [P] Update `CLAUDE.md`: fetch filter/metrics, dual detection + driver rule, provisional window, `pipeline.run`
- [X] T020 Run quickstart.md validation (`uv run pytest -q`, demo run, inspect report) and fix anything found

## Dependencies & Execution Order

- T001 → T002/T003 → US1 (T004–T010) → US2 (T011–T014) → US3 (T015–T016) → Polish.
- Within US1: T004 and T005 are parallel (different files); T006 → T007 → T008 → T009 → T010.
- US2 depends on `Anomaly.provisional` from T007; US3 depends on the final `detect()` signature.

## Parallel Example: User Story 1

```text
T004 tests/test_fetch.py + src/cost_anomaly/fetch.py
T005 tests/test_transform.py + src/cost_anomaly/transform.py
```

## Implementation Strategy

MVP = Phase 1–3 (correct data). Then US2 (latency), US3 (enabler), polish, verify, commit.
