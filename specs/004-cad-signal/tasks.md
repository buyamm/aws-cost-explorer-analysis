# Tasks: AWS Cost Anomaly Detection as a second signal

**Tests**: REQUIRED (red before green)

- [X] T001 Baseline `uv run pytest -q` (178 passed)

## User Story 1 (P1) 🎯

- [X] T002 [US1] Failing tests `tests/test_auth.py`: `session_policy(ALLOWED_OPERATIONS) == SESSION_POLICY` (single string action); `session_policy(CAD_OPERATIONS)` lists `["ce:GetAnomalies", "ce:GetCostAndUsage"]`; `assume_role_session(..., operations=CAD_OPERATIONS)` sends that policy; then implement in `src/cost_anomaly/guard.py`, `src/cost_anomaly/auth.py`
- [X] T003 [US1] Failing tests `tests/test_cad.py` with fixture `tests/fixtures/ce_anomalies.json`: request shape (`DateInterval`, `MaxResults`); parsing (dates, services from root causes, fallback to `DimensionValue`, open end → None, impact, score); pagination; page cap → `TooManyPages`; ClientError → `CostExplorerError`; then implement `src/cost_anomaly/cad.py`
- [X] T004 [US1] Failing tests `tests/test_cad.py::match` and `tests/test_report.py`: matched / unmatched / open-ended; `cad_only()`; CSV column `cad_match` (`true`/`false`/empty); then implement `match`, `cad_only`, `Anomaly.cad_match`, CSV
- [X] T005 [US1] Failing tests `tests/test_pipeline.py`: `with_cad=True` fetches CAD after costs, marks matches, allowlist permits GetAnomalies; `with_cad=False` → GetAnomalies forbidden, `cad is None`; CAD AccessDenied → `cad_error` set, anomalies unchanged with `cad_match=None`; then implement in `pipeline.py`
- [X] T006 [US1] Failing tests `tests/test_cli.py`: `--with-cad` passes `operations=CAD_OPERATIONS` to `assume_role_session` and prints a warning on `cad_error`; default passes the default set; then implement in `cli.py`
- [X] T007 [US1] Failing tests: report section "Đối chiếu AWS CAD" with counts and CAD-only table, "không lấy được" note on error, absent without CAD (`tests/test_analysis.py`); `Incident.cad_match` merged and loaded from old JSON without the key (`tests/test_state.py`); Slack line "AWS CAD cũng phát hiện" (`tests/test_alert.py`); then implement in `analysis.py`, `html_report.py`, `md_report.py`, `state.py`, `alert.py`

## Polish

- [X] T008 Demo run 2 with `--with-cad` (stub STS policy + GetAnomalies), README (pricing caveat, IAM permission), CLAUDE.md
- [X] T009 Validation: suite, demo
