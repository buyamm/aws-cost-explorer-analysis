# Quickstart: validate 001

Prerequisites: `uv sync`. Nothing here touches AWS.

1. `uv run pytest -q` — all green.
2. `uv run python demo/run_demo.py --end-date 2026-10-15`, then check the printed anomalies:
   - Fargate SP expiry → one `SPIKE`, `metric=amortized`, `driver=rate`.
   - ElastiCache RI expiry → one `SPIKE`, `metric=usage`, `driver=rate`, not `NEW_SERVICE`.
   - EC2 Compute fleet spike → `driver=usage`.
   - CloudWatch spike on 2026-10-14 (T−1) → `provisional=true`.
3. Open `demo/demo_anomalies_report.html`: rows show "tạm tính" and "do giá/coverage" badges;
   the config table lists `include_provisional` and `driver_tolerance`.
4. `uv run cost-anomaly --help` is forbidden by settings; instead
   `uv run python -c "from cost_anomaly import cli; cli.parse_args(['--help'])"` shows
   `--no-provisional`.
