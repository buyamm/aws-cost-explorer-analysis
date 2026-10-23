# Tasks: Per-service thresholds, drop alerts and month impact

**Input**: `specs/002-detection-rules/` · **Tests**: REQUIRED (constitution II, red before green)

## Phase 1: Setup

- [X] T001 Baseline `uv run pytest -q` on branch `002-detection-rules` (92 passed)

## Phase 2: Foundational

- [X] T002 Test then add to `src/cost_anomaly/config.py`: `detect_drops=True`, `drop_ratio=0.1`, `drop_min_median=10.0`, `service_overrides` (default empty mapping), `ignore`/`known` (default `frozenset()`), and `Settings.for_service(name)` returning a copy with that service's overrides (`tests/test_config.py`)

## Phase 3: User Story 1 — Per-service thresholds (P1) 🎯 MVP

- [X] T003 [US1] Failing tests `tests/test_settings_file.py` for `load_config(path, base)`: defaults applied; per-service overrides stored; `ignore`/`known` sets; errors raise `ConfigError` for unknown top-level key, unknown override key, `driver_tolerance` under a service, non-number, value ≤ 0, `min_history` not an int, `drop_ratio` ≥ 1, unreadable file, invalid TOML; then implement `src/cost_anomaly/settings_file.py`
- [X] T004 [US1] Failing tests in `tests/test_detect.py`: override `min_delta=5` flags a +$7 spike only for that service; ignored service yields nothing; known service rows have `known=True`; then use `settings.for_service` + ignore/known in `detect()` (`src/cost_anomaly/detect.py`)
- [X] T005 [US1] Failing tests in `tests/test_cli.py`: `--config` applies; explicit `--k` beats `[defaults] k`; bad config exits 2 and never calls `assume_role_session`; then change threshold flags to default `None`, add `--config` in `src/cost_anomaly/cli.py`
- [X] T006 [US1] Failing tests in `tests/test_analysis.py`: explanation and near misses use the service's own `min_delta`; ignored service absent from near misses; known row has label "đã biết"; params list each override (`service: key = value`); then update `src/cost_anomaly/analysis.py`

## Phase 4: User Story 2 — DROP (P2)

- [X] T007 [US2] Failing tests in `tests/test_detect.py` (replace `test_drop_is_ignored`): steady $100 → $3 in both measures → `DROP`, negative delta, `driver=usage`; RI purchase (usage → 0, paid −50%) → nothing; SP purchase (usage flat, paid −40%) → nothing; fully RI-covered outage (usage 0, paid 60 → 0) → `DROP` with `metric=amortized`; median below `drop_min_median` → nothing; `detect_drops=False` → nothing; then implement in `classify()`/`detect()`
- [X] T008 [US2] Failing tests: `--no-drop` in `tests/test_cli.py`; analysis DROP explanation (Vietnamese, mentions backup/outage), DROP excluded from `excess`, drop near miss; HTML DROP marker/legend and MD label in `tests/test_analysis.py`; then implement in `cli.py`, `analysis.py`, `html_report.py`, `md_report.py`

## Phase 5: User Story 3 — Month impact (P3)

- [X] T009 [P] [US3] Failing test `tests/test_dates.py::days_left_in_month` (Oct 12 → 20, Oct 31 → 1, Feb 28 2027 → 1); implement in `src/cost_anomaly/dates.py`
- [X] T010 [US3] Failing tests: `Anomaly.month_impact == delta × days_left` (`tests/test_detect.py`); CSV columns `month_impact`, `known` appended (`tests/test_report.py`); then implement in `detect.py`, `report.py`
- [X] T011 [US3] Failing tests in `tests/test_analysis.py`: ongoing rollup insight contains "nếu tiếp diễn" and the impact; table rows show month impact (HTML column "Tác động tháng", MD column); then implement

## Phase 6: Polish

- [X] T012 [P] `demo/cost-anomaly.toml` + `demo/run_demo.py`: pass `--config`; RDS +$7 spike (override 5), AWS Backup outage (DROP), Bedrock known; print `month_impact`, `known`
- [X] T013 [P] README (Vietnamese): config file section, DROP, month impact, new flags/columns, exit 2 on bad config
- [X] T014 [P] CLAUDE.md: config precedence, `for_service`, DROP rule, month impact
- [X] T015 Quickstart validation, full suite, demo

## Dependencies

T001 → T002 → US1 (T003 → T004 → T005 → T006) → US2 (T007 → T008) → US3 (T009 ∥, T010 → T011) → Polish.
