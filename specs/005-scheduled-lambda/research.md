# Research: 005-scheduled-lambda

## R1. Credentials without MFA
- **Decision**: Lambda execution role; no AssumeRole, so no session policy — least privilege is
  enforced by the role's own inline policy scoped to exact ARNs, plus the in-code allowlist.
- **Alternative**: GitHub Actions OIDC (user chose Lambda).

## R2. Avoiding re-billed retries
- Async Lambda invocations retry twice by default; Scheduler retries up to 185 times by default.
- **Decision**: `aws_lambda_function_event_invoke_config.maximum_retry_attempts = 0` and Scheduler
  `retry_policy { maximum_retry_attempts = 0 }`. A failed day is retried by the next day's run
  (state not saved).

## R3. SSM SecureString decryption
- With `alias/aws/ssm`, the key policy lets account principals decrypt via SSM; the role needs only
  `ssm:GetParameter`. Optional `slack_webhook_kms_key_arn` adds `kms:Decrypt` for a CMK.

## R4. Packaging
- `archive_file` zips `src/` (package `cost_anomaly`, excluding `__pycache__`). boto3 comes from the
  python3.12 runtime; no dependencies to vendor.

## R5. Testing Terraform without credentials
- `mock_provider "aws"` with `command = plan`; data sources mocked (`aws_caller_identity`,
  `aws_region`, `aws_partition`). IAM documents built with `jsonencode` so assertions can decode them.
