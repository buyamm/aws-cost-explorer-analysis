# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`cost-anomaly`: a CLI that pulls 90 days of AWS Cost Explorer data (DAILY, grouped by SERVICE, `UnblendedCost`, filtered to `RECORD_TYPE=Usage`) and flags per-service daily cost spikes using a robust median + MAD baseline. Results go to a CSV. The README and user-facing docs are in Vietnamese.

## Commands

```sh
uv sync                                        # install deps (Python >=3.11, boto3; pytest in dev group)
uv run pytest -q                               # all tests
uv run pytest tests/test_detect.py -q          # one file
uv run pytest tests/test_cli.py::test_end_to_end_writes_csv -q   # one test
uv run python demo/run_demo.py --end-date 2026-10-15             # offline end-to-end demo
```

No linter/formatter is configured.

## Safety constraints (enforced in `.claude/settings.json`)

- Never run the real CLI (`cost-anomaly`, `uv run cost-anomaly`, `python -m cost_anomaly`, `run.py`) or the `aws` CLI: they need MFA and each Cost Explorer request costs $0.01. The user's shell exports `AWS_PROFILE` (aws-vault `credential_process`), so even an argument-less run starts real auth; to check `run.py`/CLI behavior use `--help` only, or unset `AWS_PROFILE` and point `AWS_CONFIG_FILE` at a temp file. Use the test suite or `demo/run_demo.py` to exercise the pipeline.
- Don't read `~/.aws/**`, `.env*`, top-level `*.csv` (e.g. `anomalies.csv` holds real account cost data), or the `*_report.html`/`*_report.md` written next to them (same data).
- Tests must never touch real AWS: `tests/conftest.py` has an autouse fixture that sets dummy credentials and points `AWS_CONFIG_FILE` at a temp path. AWS responses are faked with `botocore.stub.Stubber` plus JSON fixtures in `tests/fixtures/`.

## Architecture

Pipeline in `cli.main`: `compute_windows` → `assume_role_session` → `install_guard(ce client)` → `fetch_daily_costs` → `to_matrix` → `detect` → `write_csv`. Errors from auth/fetch (`AuthError`, `BotoCoreError`, `CostExplorerError`, `TooManyPages`) exit with code 2 and no CSV is written.

**Least-privilege auth (`auth.py`, `guard.py`)** — the tool does not use boto3's built-in assume-role or credential cache. It reads `role_arn`/`source_profile`/`mfa_serial`/`external_id`/`duration_seconds` from the profile itself, prompts for MFA on every run, and calls `sts:AssumeRole` with a **session policy** that allows only `ce:GetCostAndUsage`, so even an admin role yields CE-read-only credentials. As a second layer, `install_guard` hooks botocore's `provide-client-params` event (the first event fired, before signing or sending) and raises `ForbiddenOperation` for any operation outside an allowlist. STS clients allow `AssumeRole` only; CE clients allow `GetCostAndUsage` only. Keep both layers when adding AWS calls. `assume_role_session` takes injectable `prompt` and `session_factory` for testing.

**Date windows (`dates.py`, `config.Settings`)** — all windows use Cost Explorer's half-open `[start, end)` semantics. Fetch `[today-90, today)`. The most recent 2 days are excluded because CE data is still settling. The 7 days before that (`--eval-days`, 1–58; the CLI rejects values whose earliest baseline would fall outside the lookback) are evaluated, and each evaluated day is compared against the 30 days immediately before it. `compute_windows` raises if the lookback can't cover the earliest baseline.

**Fetch/transform** — `fetch_daily_costs` follows `NextPageToken` up to `max_pages` (cost guard), then raises `TooManyPages`. `to_matrix` pivots into `{service: {day: cost}}`. It sums amounts per (service, day), because a day can be split across pages, and it zero-fills missing days, because CE omits zero-cost groups.

**Detection (`detect.py`)** — for each service × eval day:
- If the baseline has fewer than `min_history` (7) non-zero days, the day is a `NEW_SERVICE` when cost ≥ `new_threshold`. Note that a newly appearing service keeps being flagged daily until it accumulates 7 days of history.
- Otherwise robust z = (cost − median) / `robust_scale`, where `robust_scale = max(1.4826·MAD, 1% of |median|, 0.01)` so flat baselines don't divide by zero. The day is a `SPIKE` only if z > `k` (3.5) **and** delta ≥ `min_delta` ($10).

**Output** — `report.write_csv` sorts rows by (date, delta) descending. `robust_z` is blank for `NEW_SERVICE`. Unless `--no-report`, the CLI also writes `<output stem>_report.html` and `.md`:
- `analysis.build_report` is the single source for both. It re-scores cells with `detect.score`/`classify` (the same math as detection, so explanations and chart thresholds can't drift from it) and produces per-row explanations, per-service rollups (consecutive-day runs, ongoing on last eval day), near misses (unflagged days filtered by `min_delta`/`k`/`new_threshold`), chart series, and insight/next-step text.
- `html_report` renders a self-contained page: inline CSS/JS, charts drawn client-side from a JSON `<script>` block (escape `</` there; service names are untrusted), light/dark tokens. `md_report` renders the same content minus charts.
- All report prose is Vietnamese, matching the README.

## Tests and demo

`tests/conftest.py::results_from_matrix` builds CE `ResultsByTime` payloads from a `{service: {day: cost}}` dict. Use it to write detection/e2e tests instead of hand-writing JSON. CLI tests monkeypatch `cli.assume_role_session`.

`demo/run_demo.py` runs the real `cli.main` with a temp AWS config, a simulated MFA code, and stubbed STS + paginated CE responses built from synthetic data with planted scenarios. It writes `demo/demo_anomalies.csv` plus the reports.
