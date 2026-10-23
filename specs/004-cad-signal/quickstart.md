# Quickstart: validate 004

1. `uv run pytest -q` — green.
2. Demo (run 2 uses `--with-cad` with a stubbed GetAnomalies response): EC2 Compute and
   ElastiCache rows `cad_match=true`; S3 appears under "chỉ CAD" in the report; the demo prints the
   session policy containing `ce:GetAnomalies` only for that run.
