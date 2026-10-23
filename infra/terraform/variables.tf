variable "account_label" {
  description = "Name shown in reports and Slack messages; defaults to the AWS account ID"
  type        = string
  default     = ""
}

variable "aws_region" {
  description = "Region for the function, bucket and schedule (Cost Explorer itself is global)"
  type        = string
  default     = "us-east-1"
}

variable "config_toml" {
  description = "Optional cost-anomaly TOML config text ([defaults], [services.\"...\"], ignore, known)"
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for the function"
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.log_retention_days)
    error_message = "log_retention_days must be a value CloudWatch Logs supports (1, 3, 5, 7, 14, 30, 60, 90, ...)."
  }
}

variable "name_prefix" {
  description = "Prefix for every resource name (function, bucket, roles, schedule)"
  type        = string
  default     = "cost-anomaly"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}[a-z0-9]$", var.name_prefix))
    error_message = "name_prefix must be 3-32 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "report_retention_days" {
  description = "Days to keep uploaded reports in S3"
  type        = number
  default     = 90

  validation {
    condition     = var.report_retention_days >= 1
    error_message = "report_retention_days must be at least 1."
  }
}

variable "schedule_expression" {
  description = "EventBridge Scheduler expression; default 02:00 UTC = 09:00 Vietnam time"
  type        = string
  default     = "cron(0 2 * * ? *)"
}

variable "schedule_timezone" {
  description = "Time zone for schedule_expression"
  type        = string
  default     = "UTC"
}

variable "slack_webhook_kms_key_arn" {
  description = "Customer managed KMS key of the SSM parameter; leave empty for the AWS managed alias/aws/ssm"
  type        = string
  default     = ""
}

variable "slack_webhook_parameter_name" {
  description = "Name of an SSM SecureString holding the Slack webhook URL (created outside Terraform); empty disables Slack"
  type        = string
  default     = ""

  validation {
    condition     = var.slack_webhook_parameter_name == "" || startswith(var.slack_webhook_parameter_name, "/")
    error_message = "slack_webhook_parameter_name must be a full path starting with /."
  }
}

variable "with_cad" {
  description = "Also read AWS Cost Anomaly Detection anomalies (adds ce:GetAnomalies)"
  type        = bool
  default     = false
}
