# Tasks: Incidents with state and Slack alerts

**Input**: `specs/003-incidents-alerts/` · **Tests**: REQUIRED (red before green)

## Phase 1: Setup

- [X] T001 Baseline `uv run pytest -q` (137 passed)

## Phase 2: User Story 1 — Incidents and state (P1) 🎯 MVP

- [X] T002 [US1] Failing tests `tests/test_state.py` for `merge()`: new 2-day run → 1 new incident; same anomalies again → no change; next-day continuation at similar level → end extended, no change; peak +50% and ≥ min_delta → `worse` once; NEW_SERVICE 6 days → 1 incident; known service → recorded, never a change; gap day → two incidents; DROP worse compares magnitude; incidents ending before `fetch_start` pruned; then implement `src/cost_anomaly/state.py` (`Incident`, `State`, `Change`, `merge`, `mark_alerted`)
- [X] T003 [US1] Failing tests for `LocalFileStore`: missing file → empty state; round-trip save/load; corrupt JSON or unknown version → `StateError`; then implement in `state.py`
- [X] T004 [US1] Failing tests `tests/test_alerting.py` for `process()`: changes delivered then state saved with `alerted_at`; no changes → deliver not called, state still saved (merged/pruned); deliver raises `AlertError` → state not saved, error propagates; `save=False` never saves; then implement `src/cost_anomaly/alerting.py`

## Phase 3: User Story 2 — Slack (P2)

- [X] T005 [P] [US2] Failing tests `tests/test_alert.py`: `build_message` — Vietnamese header, sorted by |month_impact|, labels, new/worse, location, max 10 + "và N sự cố khác"; `validate_webhook` accepts `https://hooks.slack.com/services/...`, rejects http, other hosts, empty; `send` posts JSON once on 200; retries URLError/429/500 then succeeds; gives up after 3 → `AlertError` without the URL in the message; 400 not retried; then implement `src/cost_anomaly/alert.py`
- [X] T006 [US2] Failing tests `tests/test_cli.py`: `--state` + webhook env → one POST, state file written; second identical run → no POST; delivery failure → exit 3, CSV written, state unchanged; bad webhook → exit 2 before auth; `--alert-dry-run` prints payload, no POST, no state change; corrupt state → exit 2 before auth; then wire in `src/cost_anomaly/cli.py`

## Phase 4: User Story 3 — CI exit code (P3)

- [X] T007 [US3] Failing tests `tests/test_cli.py`: `--fail-on-anomaly` with state → 1 on first run, 0 on the repeat; without state → 1 if any non-known anomaly, 0 if only known; delivery failure + fail flag → 3; then implement

## Phase 5: Polish

- [X] T008 [P] Demo: two runs with temp `--state` (end date − 1, then end date with `--alert-dry-run`), print dedup result
- [X] T009 [P] README (Vietnamese): incidents/state, Slack setup (create incoming webhook, env var), exit codes, cron example
- [X] T010 [P] CLAUDE.md: state/alerting modules, exit codes, no-network test rule
- [X] T011 Quickstart validation, full suite, demo

## Dependencies

T001 → T002 → T003 → T004 → (T005 ∥) → T006 → T007 → Polish.
