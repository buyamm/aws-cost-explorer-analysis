# Contract: CLI flags, state file, Slack message (003)

## Flags and environment

| Flag / env | Effect |
|------------|--------|
| `--state PATH` | Load/save incidents JSON; alert only new/worse incidents |
| `--fail-on-anomaly` | Exit 1 when there is something new |
| `--alert-dry-run` | Print the Slack payload; do not send; do not save state |
| `COST_ANOMALY_SLACK_WEBHOOK` | Slack incoming webhook (`https://hooks.slack.com/...`) |

Exit codes: 0 ok · 1 new anomalies (with `--fail-on-anomaly`) · 2 args/config/state/webhook/auth/fetch
error · 3 Slack delivery failed (CSV/report written, state not saved).

## State file

```json
{
  "version": 1,
  "incidents": [
    {
      "id": "Amazon EC2|SPIKE|2026-10-11",
      "service": "Amazon EC2",
      "kind": "SPIKE",
      "start": "2026-10-11",
      "end": "2026-10-12",
      "peak_delta": 228.91,
      "last_alerted_peak": 228.91,
      "alerted_at": "2026-10-15T08:00:00+00:00",
      "month_impact": 4578.2,
      "driver": "usage",
      "provisional": false,
      "known": false
    }
  ]
}
```

## Slack payload (shape)

```json
{
  "text": "cost-anomaly: 2 sự cố chi phí mới/xấu đi (profile project-cost)",
  "blocks": [
    {"type": "header", "text": {"type": "plain_text", "text": "Chi phí AWS bất thường: 2 sự cố"}},
    {"type": "section", "text": {"type": "mrkdwn", "text": "*SPIKE · Amazon EC2* (mới)\n2026-10-11 → 2026-10-12 · vượt $228.91/ngày · nếu tiếp diễn +$4,578.20 tháng này"}},
    {"type": "context", "elements": [{"type": "mrkdwn", "text": "Report: anomalies_report.html"}]}
  ]
}
```
