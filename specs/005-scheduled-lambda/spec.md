# Feature Specification: Scheduled run on AWS Lambda (Terraform)

**Feature Branch**: `005-scheduled-lambda`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "Research direction 4: run on a schedule without MFA. Lambda + EventBridge Scheduler in the project account, a role that only has ce:GetCostAndUsage; keep the session policy idea and the allowlist. State in S3, Slack webhook in SSM SecureString, infrastructure in Terraform."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Daily alerts with nobody at the keyboard (Priority: P1)

An engineer deploys the tool once into the project account with Terraform. Every day at 09:00
Vietnam time it fetches costs, updates incidents in S3, uploads the reports, and posts new or
worsened incidents to Slack — no MFA prompt, no laptop.

**Why this priority**: Alerts only matter if they run unattended (risk 2 in the research).

**Independent Test**: Invoke the handler with stubbed Cost Explorer, S3 and SSM: it reads state,
writes state and three report files, fetches the webhook once, and posts one Slack message.

**Acceptance Scenarios**:

1. **Given** the deployed function, **When** the schedule fires, **Then** it runs the same
   pipeline as the CLI with the execution role's credentials (no AssumeRole, no prompt).
2. **Given** a state object in S3, **Then** the run uses it for deduplication and writes it back
   only after Slack delivery succeeded.
3. **Given** a successful run, **Then** CSV, HTML and Markdown reports are uploaded under
   `reports/<date>/` and the Slack message points there.
4. **Given** no Slack parameter configured, **Then** incidents are still tracked and the summary
   is logged.
5. **Given** Slack delivery fails, **Then** the invocation fails (visible in CloudWatch), state is
   not written, and there is no automatic retry that would re-bill Cost Explorer requests.

---

### User Story 2 - Least privilege by construction (Priority: P1)

The function's role can call only the Cost Explorer read operation(s) it needs, read/write only
its state object and reports prefix, read only the one SSM parameter, and write only its own
logs. Every client in the code is still wrapped by the operation allowlist.

**Independent Test**: Terraform unit tests (mocked provider) assert the role policy's actions and
resources; Python tests assert forbidden calls (e.g. S3 DeleteObject) fail before being sent.

**Acceptance Scenarios**:

1. **Given** default variables, **Then** the policy allows exactly `ce:GetCostAndUsage`,
   `s3:GetObject`/`s3:PutObject` scoped to the state key and reports prefix, log writes to its log
   group, and nothing else.
2. **Given** `with_cad = true`, **Then** `ce:GetAnomalies` is added; otherwise absent.
3. **Given** a Slack parameter name, **Then** `ssm:GetParameter` on that parameter only is added.
4. **Given** the state bucket, **Then** it blocks public access, enforces TLS, encrypts at rest,
   versions objects, and expires old reports.
5. **Given** the Slack webhook, **Then** Terraform never holds its value (the user writes it to SSM
   directly), so it is not in Terraform state.

### Edge Cases

- First run: the state object does not exist → empty state.
- Corrupt state object → invocation fails with a clear error; nothing is overwritten.
- Concurrency: at most one invocation at a time.
- Config (thresholds, ignore/known) passed as TOML text in an environment variable; invalid →
  invocation fails before any Cost Explorer call.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A Lambda handler MUST run `pipeline.run` with the default credential chain and the
  settings from optional TOML config text.
- **FR-002**: State MUST be stored as the same JSON document in S3 (`GetObject`/`PutObject`),
  with "not found" treated as empty.
- **FR-003**: Reports (CSV, HTML, MD) MUST be uploaded to `s3://<bucket>/<prefix><date>/`.
- **FR-004**: The webhook MUST be read from SSM SecureString (`GetParameter` with decryption) and
  validated; never logged.
- **FR-005**: Every boto3 client in the handler MUST be guarded: CE {GetCostAndUsage
  [+GetAnomalies]}, S3 {GetObject, PutObject}, SSM {GetParameter}.
- **FR-006**: Terraform MUST create: Lambda (python3.12, code zipped from `src/`), log group with
  retention, IAM role with least-privilege inline policy, S3 bucket (versioning, SSE, public
  access block, TLS-only policy, lifecycle), EventBridge Scheduler schedule (default daily 02:00
  UTC) with its own invoke role, no retries anywhere, reserved concurrency 1.
- **FR-007**: Terraform MUST NOT create or read the webhook value.
- **FR-008**: Terraform unit tests MUST run with a mocked provider (no credentials) and cover
  policy actions/resources, CAD/Slack toggles, bucket hardening, schedule and variable validation.
- **FR-009**: README MUST document deployment (`terraform apply` by the user), writing the SSM
  parameter, costs, and how to invoke once manually.

## Success Criteria *(mandatory)*

- **SC-001**: `terraform fmt -check`, `validate` and `test` pass locally without AWS credentials.
- **SC-002**: The handler test proves exactly one Cost Explorer request for a one-page account.
- **SC-003**: Monthly cost of the deployment: ~30–60 Cost Explorer requests (≈ $0.30–0.60); Lambda,
  Scheduler, S3 and SSM standard parameter within free tier or cents.

## Assumptions

- Deployed in the account whose costs are analysed (member account): Cost Explorer must be enabled.
- SSM parameter uses the AWS managed key `alias/aws/ssm` (no extra KMS permission needed); a
  customer managed key can be passed as an optional variable.
- `terraform apply` is run by the user; this feature only provides and tests the code.
