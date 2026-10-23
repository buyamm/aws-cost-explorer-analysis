# Quickstart: validate 002

1. `uv run pytest -q` — green.
2. `uv run python demo/run_demo.py --end-date 2026-10-15` (demo passes `--config demo/cost-anomaly.toml`):
   - RDS +$7 spike reported thanks to `min_delta = 5`; Lambda +$7 still filtered.
   - Backup (AWS Backup) $40 → $0 reported as `DROP` with negative `month_impact`.
   - Bedrock rows have `known=true`.
   - Fargate SP expiry / ElastiCache RI expiry: no DROP rows.
3. Report: DROP marker in charts, "đã biết" tag, "nếu tiếp diễn" sentence, overrides in the config table.
4. `--config` pointing at a file with `foo = 1` → exit 2, no AWS call.
