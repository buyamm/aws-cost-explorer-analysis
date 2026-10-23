# Quickstart: validate 005

1. `uv run pytest -q` — handler tests with stubbed CE/S3/SSM pass.
2. `terraform -chdir=infra/terraform init -backend=false` (downloads providers only), then
   `terraform -chdir=infra/terraform fmt -check -recursive`, `validate`, `test` — all pass without
   AWS credentials (mock provider, plan mode).
3. Deployment itself (`terraform apply`, `aws ssm put-parameter`) is done by the user (README).
