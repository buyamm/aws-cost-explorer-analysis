# Implementation Plan: Incidents with state and Slack alerts

**Branch**: `003-incidents-alerts` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

## Summary

`state.py`: `Incident`, `State`, `StateError`, `LocalFileStore(path)` (`load()`, `save(state)`),
`merge(state, anomalies, settings, fetch_start) -> (State, list[Change])`,
`mark_alerted(state, changes, now) -> State`. `alert.py`: `build_message(changes, profile,
location) -> dict`, `send(url, payload, opener=urlopen, sleep=time.sleep)`, `webhook_from_env()`,
`AlertError`. `alerting.py`: `process(anomalies, settings, fetch_start, store, deliver, now,
save=True) -> list[Change]` (load → merge → deliver if changes → mark → save). CLI wires flags
`--state PATH`, `--fail-on-anomaly`, `--alert-dry-run`.

## Technical Context

Python ≥ 3.11 · stdlib only (`json`, `urllib.request`, `time`) · pytest with monkeypatched opener ·
CLI · constraints: no network in tests, secret never on argv/logs.

## Constitution Check

| Principle | Status |
|-----------|--------|
| I. Least privilege | PASS: Slack is outbound HTTPS, no AWS permission added |
| II. Test-first | PASS |
| III. No real AWS / network | PASS: opener injected and faked |
| IV. API cost | PASS: no extra requests |
| V. Explainable | PASS: incident rules are plain comparisons, documented |
| VI. Simplicity | PASS: stdlib `urllib`; no Slack SDK |
| Constraint: secrets | PASS: env var only, host allowlist, never printed |

## Design notes

- Incident key = (service, kind); runs from `analysis.runs_of`. A run attaches to an incident of
  the same key if `run.start <= inc.end + 1 day` and `run.end >= inc.start - 1 day`.
- Worse: `abs(peak) >= 1.5 × abs(last_alerted_peak)` and
  `abs(peak) - abs(last_alerted_peak) >= settings.for_service(service).min_delta`.
- Incident id: `f"{service}|{kind}|{start}"` stable for the first start date.
- JSON: `{"version": 1, "incidents": [...]}` with ISO dates; unknown version/corrupt → `StateError`
  → exit 2 (before auth, since it's loaded first).
- Exit code: 3 if delivery failed; else 1 if `--fail-on-anomaly` and something new; else 0.
- Webhook validated at start (before auth) when set and not dry-run.
- `send`: POST `application/json`, timeout 10, 3 attempts, backoff 1 s, 2 s; retry on `URLError`,
  `HTTPError` 429/5xx; error messages carry status/reason only.

## Project Structure

`src/cost_anomaly/{state,alert,alerting}.py` (new), `cli.py`; tests `test_state.py`,
`test_alert.py`, `test_alerting.py`, `test_cli.py`; demo two runs + dry-run.

## Complexity Tracking

None.
