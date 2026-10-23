# Tasks: Scheduled run on AWS Lambda (Terraform)

**Tests**: REQUIRED (red before green; Terraform tests before HCL)

- [X] T001 Baseline `uv run pytest -q` (200 passed); `terraform version` ≥ 1.13

## User Story 1 — Handler (P1)

- [X] T002 [US1] Failing tests `tests/test_settings_file.py`: `parse_config(text, base, source)` matches `load_config` and errors name the source; refactor `load_config` onto it
- [X] T003 [US1] Failing tests `tests/test_state.py` for `S3StateStore`: NoSuchKey → empty; round-trip put/get (Stubber, `ContentType` JSON); corrupt body → `StateError` naming `s3://bucket/key`; other ClientError propagates as `StateError`; then implement in `state.py`
- [X] T004 [US1] Failing tests `tests/test_lambda_handler.py`: full run with stubbed CE (1 page), S3 (get state, put 3 reports, put state), SSM (GetParameter WithDecryption) and fake urlopen → 1 Slack POST, summary dict; no Slack param → no SSM call, summary logged; Slack failure → raises `AlertError`, state not put; invalid config env → raises before CE call; guarded clients reject S3 `DeleteObject`; `WITH_CAD=true` uses CAD operations; then implement `src/cost_anomaly/lambda_handler.py`

## User Story 2 — Terraform (P1)

- [X] T005 [US2] Write `infra/terraform/tests/defaults_unit_test.tftest.hcl` (mock provider, plan): exact policy actions by default; CAD adds `ce:GetAnomalies`; Slack param adds scoped `ssm:GetParameter`; KMS key adds `kms:Decrypt`; S3 resources scoped to state key and reports prefix; bucket public access block all true; versioning enabled; SSE; TLS-only bucket policy; lifecycle expiry; schedule expression/timezone and retry 0; lambda event invoke retries 0; reserved concurrency 1; runtime/handler; env vars; invalid `name_prefix`/`log_retention_days` rejected — run `terraform test` and watch it fail
- [X] T006 [US2] Implement `infra/terraform/*.tf` until `terraform fmt -check`, `validate`, `test` pass; add `infra/terraform/.gitignore` (state, `.terraform/`, `build/`), commit `.terraform.lock.hcl`

## Polish

- [X] T007 README (Vietnamese) deployment section; replace the "spec 005" pointer in README; CLAUDE.md (handler, infra, safety: never `terraform apply`)
- [X] T008 Validation: pytest, terraform fmt/validate/test, demo
