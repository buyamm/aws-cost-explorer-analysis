# Research: 004-cad-signal

## R1. GetAnomalies API
- Request: `DateInterval` (required; anomalies whose end date falls in it), optional `MonitorArn`,
  `Feedback`, `TotalImpact`, `MaxResults`, `NextPageToken`.
- Response: `Anomalies[]` with `AnomalyId`, `AnomalyStartDate`, `AnomalyEndDate`, `DimensionValue`,
  `RootCauses[]` (`Service`, `Region`, `LinkedAccount`, `UsageType`, `Impact.Contribution`),
  `AnomalyScore{MaxScore, CurrentScore}`, `Impact{MaxImpact, TotalImpact, ...}`, `MonitorArn`;
  `NextPageToken`.
- **Decision**: no monitor filter (all monitors visible to the account); page cap = `max_pages`.

## R2. Pricing
- Not documented whether GetAnomalies is billed like GetCostAndUsage ($0.01). **Decision**:
  opt-in flag; README tells users to check the Cost Explorer API line on the bill.

## R3. Failure policy
- **Decision**: CAD errors (ClientError/BotoCoreError/TooManyPages/ForbiddenOperation) become a
  warning; the primary signal must not depend on the secondary one.
