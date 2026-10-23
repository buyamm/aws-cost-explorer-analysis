# Data Model: 005-scheduled-lambda

- **S3 objects**: `state/incidents.json` (state JSON v1 from 003), `reports/<YYYY-MM-DD>/anomalies.csv`,
  `anomalies_report.html`, `anomalies_report.md`.
- **SSM parameter**: SecureString holding the Slack webhook URL (created by the user).
- **Handler result**: `{"date", "anomalies", "alerted", "cad_error", "reports"}`.
