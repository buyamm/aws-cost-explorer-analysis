# Plan-mode unit tests with a mocked AWS provider: no credentials, nothing is created.

mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
    }
  }

  mock_data "aws_region" {
    defaults = {
      region = "us-east-1"
    }
  }

  mock_data "aws_partition" {
    defaults = {
      partition = "aws"
    }
  }
}

variables {
  name_prefix = "cost-anomaly"
}

run "role_policy_is_least_privilege_by_default" {
  command = plan

  assert {
    condition = toset(flatten([for s in jsondecode(aws_iam_role_policy.lambda.policy).Statement : s.Action])) == toset([
      "ce:GetCostAndUsage", "s3:GetObject", "s3:PutObject", "logs:CreateLogStream", "logs:PutLogEvents",
    ])
    error_message = "Lambda role must only read Cost Explorer, read/write its S3 objects and write its logs"
  }

  assert {
    condition = toset(one([for s in jsondecode(aws_iam_role_policy.lambda.policy).Statement : s.Resource if s.Sid == "StateAndReports"])) == toset([
      "arn:aws:s3:::cost-anomaly-123456789012-us-east-1/state/incidents.json",
      "arn:aws:s3:::cost-anomaly-123456789012-us-east-1/reports/*",
    ])
    error_message = "S3 access must be limited to the state object and the reports prefix"
  }

  assert {
    condition = one([for s in jsondecode(aws_iam_role_policy.lambda.policy).Statement : s.Resource if s.Sid == "Logs"]) == [
      "arn:aws:logs:us-east-1:123456789012:log-group:/aws/lambda/cost-anomaly:*",
    ]
    error_message = "Log writes must be limited to the function's own log group"
  }

  assert {
    condition     = !contains(keys(aws_lambda_function.main.environment[0].variables), "SLACK_WEBHOOK_PARAMETER")
    error_message = "Without a parameter name, the function must not look for a Slack webhook"
  }
}

run "cad_adds_get_anomalies" {
  command = plan

  variables {
    with_cad = true
  }

  assert {
    condition     = contains(one([for s in jsondecode(aws_iam_role_policy.lambda.policy).Statement : s.Action if s.Sid == "CostExplorer"]), "ce:GetAnomalies")
    error_message = "with_cad must allow ce:GetAnomalies"
  }

  assert {
    condition     = aws_lambda_function.main.environment[0].variables["WITH_CAD"] == "true"
    error_message = "with_cad must be passed to the function"
  }
}

run "slack_parameter_is_read_only_and_scoped" {
  command = plan

  variables {
    slack_webhook_parameter_name = "/cost-anomaly/slack-webhook"
    slack_webhook_kms_key_arn    = "arn:aws:kms:us-east-1:123456789012:key/abcd"
  }

  assert {
    condition = one([for s in jsondecode(aws_iam_role_policy.lambda.policy).Statement : s if s.Sid == "SlackWebhook"]) == {
      Sid      = "SlackWebhook"
      Effect   = "Allow"
      Action   = ["ssm:GetParameter"]
      Resource = ["arn:aws:ssm:us-east-1:123456789012:parameter/cost-anomaly/slack-webhook"]
    }
    error_message = "Only ssm:GetParameter on the one webhook parameter is allowed"
  }

  assert {
    condition     = one([for s in jsondecode(aws_iam_role_policy.lambda.policy).Statement : s.Resource if s.Sid == "SlackWebhookKey"]) == ["arn:aws:kms:us-east-1:123456789012:key/abcd"]
    error_message = "A customer managed key must be decryptable, and only that key"
  }

  assert {
    condition     = aws_lambda_function.main.environment[0].variables["SLACK_WEBHOOK_PARAMETER"] == "/cost-anomaly/slack-webhook"
    error_message = "The parameter name (not its value) must be passed to the function"
  }
}

run "bucket_is_private_encrypted_versioned_and_tls_only" {
  command = plan

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.state.block_public_acls,
      aws_s3_bucket_public_access_block.state.block_public_policy,
      aws_s3_bucket_public_access_block.state.ignore_public_acls,
      aws_s3_bucket_public_access_block.state.restrict_public_buckets,
    ])
    error_message = "All public access must be blocked"
  }

  assert {
    condition     = aws_s3_bucket_versioning.state.versioning_configuration[0].status == "Enabled"
    error_message = "State bucket must be versioned so a bad write can be rolled back"
  }

  assert {
    condition     = one(one(aws_s3_bucket_server_side_encryption_configuration.state.rule).apply_server_side_encryption_by_default).sse_algorithm == "AES256"
    error_message = "State bucket must be encrypted at rest"
  }

  assert {
    condition     = jsondecode(aws_s3_bucket_policy.state.policy).Statement[0].Condition.Bool["aws:SecureTransport"] == "false"
    error_message = "Bucket policy must deny non-TLS requests"
  }

  assert {
    condition     = one([for r in aws_s3_bucket_lifecycle_configuration.state.rule : r.expiration[0].days if r.id == "expire-reports"]) == 90
    error_message = "Reports must expire after report_retention_days"
  }
}

run "schedule_runs_daily_without_retries" {
  command = plan

  assert {
    condition     = aws_scheduler_schedule.daily.schedule_expression == "cron(0 2 * * ? *)" && aws_scheduler_schedule.daily.schedule_expression_timezone == "UTC"
    error_message = "Default schedule is 02:00 UTC (09:00 Vietnam time) daily"
  }

  assert {
    condition     = aws_scheduler_schedule.daily.target[0].retry_policy[0].maximum_retry_attempts == 0
    error_message = "Scheduler must not retry: each retry re-bills Cost Explorer requests"
  }

  assert {
    condition     = aws_lambda_function_event_invoke_config.main.maximum_retry_attempts == 0
    error_message = "Async invocations must not be retried"
  }

  assert {
    condition     = aws_lambda_function.main.reserved_concurrent_executions == 1
    error_message = "Only one run at a time, so two runs never race on the state object"
  }

  assert {
    condition     = aws_lambda_function.main.runtime == "python3.12" && aws_lambda_function.main.handler == "cost_anomaly.lambda_handler.handler"
    error_message = "Function must run the packaged handler on python3.12"
  }

  assert {
    condition     = aws_cloudwatch_log_group.lambda.retention_in_days == 30
    error_message = "Logs must be retained 30 days by default"
  }
}

run "rejects_invalid_name_prefix" {
  command = plan

  variables {
    name_prefix = "Cost_Anomaly"
  }

  expect_failures = [var.name_prefix]
}

run "rejects_unsupported_log_retention" {
  command = plan

  variables {
    log_retention_days = 31
  }

  expect_failures = [var.log_retention_days]
}
