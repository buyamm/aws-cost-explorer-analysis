# Contract: Terraform module `infra/terraform` (005)

## Variables
| Name | Type | Default |
|------|------|---------|
| `aws_region` | string | `us-east-1` |
| `name_prefix` | string | `cost-anomaly` (lowercase, digits, hyphens) |
| `schedule_expression` | string | `cron(0 2 * * ? *)` |
| `schedule_timezone` | string | `UTC` |
| `with_cad` | bool | `false` |
| `slack_webhook_parameter_name` | string | `""` (no Slack) |
| `slack_webhook_kms_key_arn` | string | `""` |
| `config_toml` | string | `""` |
| `account_label` | string | `""` → account id |
| `log_retention_days` | number | `30` (CloudWatch allowed values) |
| `report_retention_days` | number | `90` |

## Outputs
`function_name`, `state_bucket`, `schedule_name`, `log_group_name`.

## Handler
`cost_anomaly.lambda_handler.handler`; env as in plan.md.
