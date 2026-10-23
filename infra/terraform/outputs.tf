output "function_name" {
  description = "Lambda function to invoke manually: aws lambda invoke --function-name <this> out.json"
  value       = aws_lambda_function.main.function_name
}

output "log_group_name" {
  description = "CloudWatch log group with each run's summary"
  value       = aws_cloudwatch_log_group.lambda.name
}

output "schedule_name" {
  description = "EventBridge Scheduler schedule that runs the function"
  value       = aws_scheduler_schedule.daily.name
}

output "state_bucket" {
  description = "S3 bucket holding state/incidents.json and reports/<date>/"
  value       = aws_s3_bucket.state.bucket
}
