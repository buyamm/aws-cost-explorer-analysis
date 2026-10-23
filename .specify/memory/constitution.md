# cost-anomaly Constitution

## Core Principles

### I. Two-Layer Least Privilege

Every AWS call MUST be constrained by two independent layers:

- The STS session policy passed to `AssumeRole` MUST allow only the actions the run needs.
  Where the run cannot use a session policy (for example a Lambda execution role), the IAM
  role policy itself MUST list only those actions and scope them to exact resource ARNs.
- Every boto3 client MUST be wrapped with `guard.install_guard` and an explicit operation
  allowlist, so a forbidden call fails before it is signed or sent.
- Adding an AWS operation MUST update both layers in the same change, with tests asserting
  that nothing outside the allowlist is permitted. Operations not needed by every run MUST
  be opt-in and absent from both layers when the option is off.

Rationale: the tool often runs with an admin-capable role; the blast radius must stay at
"read Cost Explorer" even if the code has a bug.

### II. Test-First (NON-NEGOTIABLE)

Production code is written only to make a failing test pass (superpowers
`test-driven-development`): write the test, watch it fail with `uv run pytest`, write the
minimal code, then refactor. Bug fixes start with a test that reproduces the bug.

### III. No Real AWS in Tests or Development

- Tests MUST fake AWS with `botocore.stub.Stubber` and JSON fixtures; the autouse fixture in
  `tests/conftest.py` keeps real credentials and config unreachable. Outbound HTTP (for
  example Slack) MUST be faked by monkeypatching.
- Agents and contributors MUST NOT run the real CLI, the `aws` CLI, or `terraform apply`, and
  MUST NOT read real cost data (top-level `*.csv`, `*_report.html`, `*_report.md`), `~/.aws`,
  or `.env*`. Use the test suite and `demo/run_demo.py` to exercise the pipeline.

### IV. API Cost Control

Each Cost Explorer request costs $0.01. Every paginated fetch MUST have a page cap that
raises instead of looping on. Any change that adds requests MUST state the per-run and
per-month cost in its plan and in the README. Paid or unknown-cost APIs MUST be opt-in.

### V. Transparent, Explainable Detection

Detection MUST stay explainable from simple statistics (median, MAD, robust z-score,
explicit thresholds) that the report can show number by number. The CSV, reports and alerts
MUST derive from one scoring path (`detect.score` / `classify` and their per-service
settings) so explanations and thresholds cannot drift from what was flagged.

### VI. Simplicity

Runtime dependencies are the standard library plus boto3. A new dependency requires a
written justification in the plan. Prefer small modules with injectable collaborators
(sessions, clocks, HTTP openers, stores) over frameworks.

## Additional Constraints

- Python >= 3.11, managed with `uv`; infrastructure as code in Terraform.
- User-facing text (README, HTML/Markdown reports, CLI help where prose, alert messages) is
  Vietnamese. Engineering artifacts (code, specs, plans) may be English.
- Secrets (for example the Slack webhook URL) MUST never be accepted via argv, printed, logged,
  or stored in Terraform state; read them from the environment or SSM SecureString.
- Exit codes are part of the interface: 0 success, 1 anomalies found when requested,
  2 auth/fetch error, 3 alert delivery failed. Changing them requires a MINOR or MAJOR bump of
  the tool version and a README update.

## Development Workflow

- Features go through Spec Kit: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement`, with specs under `specs/`.
- Before claiming a feature done: `uv run pytest -q` passes, `demo/run_demo.py` runs, and for
  Terraform changes `terraform fmt -check`, `validate` and `test` pass (mock providers only).
- README, CLAUDE.md and the demo are updated in the same change as the behavior they describe.
- One commit (or a short series) per spec on its feature branch.

## Governance

This constitution supersedes conflicting practices. Every plan's Constitution Check MUST
evaluate principles I–VI; a violation needs an entry in the plan's Complexity Tracking with
the simpler alternative that was rejected and why.

Amendments are made with `/speckit-constitution`, recorded with a version bump:
MAJOR for removing or redefining a principle, MINOR for adding a principle or materially
expanding guidance, PATCH for wording. Runtime guidance for agents lives in `CLAUDE.md`.

**Version**: 1.0.0 | **Ratified**: 2026-10-23 | **Last Amended**: 2026-10-23
