locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  region     = data.aws_region.current.region

  function_name  = var.name_prefix
  log_group_name = "/aws/lambda/${local.function_name}"
  bucket_name    = "${var.name_prefix}-${local.account_id}-${local.region}"
  bucket_arn     = "arn:${local.partition}:s3:::${local.bucket_name}"
  state_key      = "state/incidents.json"
  report_prefix  = "reports/"

  # Built with jsonencode (not aws_iam_policy_document) so plan-mode tests with a mocked provider can read it.
  lambda_policy_statements = concat(
    [
      {
        Sid      = "CostExplorer"
        Effect   = "Allow"
        Action   = var.with_cad ? ["ce:GetAnomalies", "ce:GetCostAndUsage"] : ["ce:GetCostAndUsage"]
        Resource = ["*"] # Cost Explorer has no resource-level permissions
      },
      {
        Sid      = "StateAndReports"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = ["${local.bucket_arn}/${local.state_key}", "${local.bucket_arn}/${local.report_prefix}*"]
      },
      {
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:${local.log_group_name}:*"]
      },
    ],
    var.slack_webhook_parameter_name == "" ? [] : [
      {
        Sid      = "SlackWebhook"
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = ["arn:${local.partition}:ssm:${local.region}:${local.account_id}:parameter${var.slack_webhook_parameter_name}"]
      },
    ],
    var.slack_webhook_kms_key_arn == "" ? [] : [
      {
        Sid      = "SlackWebhookKey"
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = [var.slack_webhook_kms_key_arn]
      },
    ],
  )

  lambda_environment = merge(
    {
      STATE_BUCKET  = local.bucket_name
      STATE_KEY     = local.state_key
      REPORT_PREFIX = local.report_prefix
      WITH_CAD      = tostring(var.with_cad)
      ACCOUNT_LABEL = var.account_label != "" ? var.account_label : local.account_id
    },
    var.slack_webhook_parameter_name == "" ? {} : { SLACK_WEBHOOK_PARAMETER = var.slack_webhook_parameter_name },
    var.config_toml == "" ? {} : { COST_ANOMALY_CONFIG = var.config_toml },
  )
}
