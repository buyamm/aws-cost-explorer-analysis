# Quickstart: validate 003

1. `uv run pytest -q` — green; no network (urlopen faked).
2. `uv run python demo/run_demo.py --end-date 2026-10-15` — the demo runs twice with a temp
   `--state`:
   - run 1 (end 2026-10-14, no webhook) records incidents and prints the stdout summary;
   - run 2 (end 2026-10-15, `--alert-dry-run`) prints a Slack payload with only incidents that
     are new or worse (e.g. the CloudWatch provisional spike), not the ones already alerted.
3. Corrupt state file → exit 2. Non-Slack webhook URL → exit 2.
