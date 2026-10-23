# Implementation Plan: Scheduled run on AWS Lambda (Terraform)

**Branch**: `005-scheduled-lambda` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

## Summary

Python: `settings_file.parse_config(text, base, source)`; `state.S3StateStore(client, bucket,
key)`; `lambda_handler.handler(event, context)` built on `run_scheduled(env, session, now)` for
testability. Terraform in `infra/terraform/` (style-guide layout) with plan-mode unit tests using
`mock_provider "aws"`.

## Technical Context

Python ≥ 3.11 locally, Lambda python3.12 (bundled boto3) · Terraform ≥ 1.13, hashicorp/aws ~> 6.0,
hashicorp/archive ~> 2.7 · pytest + Stubber; `terraform test`.

## Constitution Check

| Principle | Status |
|-----------|--------|
| I. Least privilege | PASS: no session policy possible without AssumeRole, so the role policy itself is minimal and ARN-scoped (constitution I allows this); all clients guarded |
| II. Test-first | PASS: pytest for the handler, `terraform test` written before the HCL |
| III. No real AWS | PASS: Stubber; mock provider; no apply |
| IV. API cost | PASS: retries disabled (Scheduler and async invoke) to avoid re-billing; cost in README |
| V. Explainable | PASS: same pipeline/report |
| VI. Simplicity | PASS: no Lambda layer, boto3 from runtime |
| Secrets | PASS: webhook only in SSM, never in TF state or logs |

## Design

- Env: `STATE_BUCKET`, `STATE_KEY` (default `state/incidents.json`), `REPORT_PREFIX` (`reports/`),
  `SLACK_WEBHOOK_PARAMETER` (optional), `WITH_CAD` (`true`/`false`), `COST_ANOMALY_CONFIG` (TOML
  text, optional), `ACCOUNT_LABEL` (shown in reports/Slack).
- Handler order: config → load state (fails early on corrupt) → pipeline → reports to S3 → webhook
  from SSM → `alerting.process` → return summary dict.
- IAM policy via `jsonencode` locals (testable under mocks); `concat` optional statements.

## Project Structure

```text
src/cost_anomaly/{lambda_handler.py (new), state.py, settings_file.py}
tests/test_lambda_handler.py (new), tests/test_state.py, tests/test_settings_file.py
infra/terraform/{terraform.tf,providers.tf,variables.tf,locals.tf,main.tf,outputs.tf}
infra/terraform/tests/defaults_unit_test.tftest.hcl
```

## Complexity Tracking

None.
