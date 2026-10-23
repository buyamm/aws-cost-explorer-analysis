# Implementation Plan: AWS Cost Anomaly Detection as a second signal

**Branch**: `004-cad-signal` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

## Summary

`guard.CAD_OPERATIONS = ALLOWED_OPERATIONS | {"GetAnomalies"}`; `auth.session_policy(operations)`
builds the STS policy from the same set, `assume_role_session(..., operations=...)`. New `cad.py`:
`CadAnomaly`, `fetch_anomalies(client, start, end, max_pages)`, `match(anomalies, cad, window_end)`.
`pipeline.run(..., with_cad=False)` installs the matching allowlist, fetches CAD after cost data,
catches CAD errors into `RunResult.cad_error`. CSV `cad_match`; report section; Slack note via
`Incident.cad_match`.

## Technical Context

Python ≥ 3.11 · boto3 `ce.get_anomalies` · pytest + Stubber · CLI.

## Constitution Check

| Principle | Status |
|-----------|--------|
| I. Least privilege | PASS: one operation added, opt-in, in both layers from one source of truth |
| II. Test-first | PASS |
| III. No real AWS | PASS: Stubber + `tests/fixtures/ce_anomalies.json` |
| IV. API cost | PASS: opt-in (unknown price), page cap, documented |
| V. Explainable | PASS: CAD shown as a separate signal, not mixed into the score |
| VI. Simplicity | PASS |

## Design

- `GetAnomalies(DateInterval={StartDate: first eval day, EndDate: last eval day}, MaxResults=100,
  NextPageToken)`; dates parsed from the first 10 chars (`YYYY-MM-DD`).
- Services = `{rc["Service"] for rc in RootCauses if "Service" in rc}` or `{DimensionValue}`.
- `match`: `replace(a, cad_match=any(a.service in c.services and c.start <= a.date <= (c.end or window_end)))`.
- CAD-only = CAD anomalies with no matched tool anomaly (any service/day overlap).
- `Anomaly.cad_match: bool | None = None`; `Incident.cad_match: bool = False` (optional in JSON).

## Project Structure

`src/cost_anomaly/{guard,auth,cad(new),pipeline,cli,detect,report,analysis,html_report,md_report,state,alert}.py`;
tests `test_cad.py` (new), `test_auth.py`, `test_pipeline.py`, `test_cli.py`, `test_analysis.py`,
`test_alert.py`; fixture `tests/fixtures/ce_anomalies.json`; demo.

## Complexity Tracking

None.
