# Research: 003-incidents-alerts

## R1. Slack delivery
- **Decision**: incoming webhook, POST JSON with `text` (fallback/notification) + Block Kit
  `blocks`; stdlib `urllib.request`. Slack returns 200 "ok"; 4xx for bad payload/revoked hook
  (not retried), 429/5xx retried.
- **Alternatives**: `slack_sdk` (dependency, constitution VI); SNS (needs AWS permission and topic;
  rejected by the user in favour of webhook).

## R2. Secret handling
- **Decision**: env var `COST_ANOMALY_SLACK_WEBHOOK` only; host must be `hooks.slack.com` over
  https (prevents sending cost data to an arbitrary URL from a mistyped/poisoned env); never
  echoed. In Lambda (005) it comes from SSM SecureString.

## R3. Dedup model
- **Decision**: incidents keyed by (service, kind), merged by day adjacency; "worse" threshold =
  +50% and ≥ service `min_delta`. Keeps alerts rare but escalations visible.
- **Alternatives**: per-(service, day) seen set (still re-alerts each new day of a long incident);
  any peak increase (too chatty with noise).

## R4. Corrupt state
- **Decision**: fail with exit 2. Silently resetting would re-send every open incident.
