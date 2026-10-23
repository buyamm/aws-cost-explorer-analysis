# Data Model: 003-incidents-alerts

## Incident
| Field | Type | Notes |
|-------|------|-------|
| id | str | `service|kind|first start` |
| service, kind | str | key |
| start, end | date | inclusive |
| peak_delta | float | largest magnitude delta seen (sign kept) |
| last_alerted_peak | float \| None | None = never reported |
| alerted_at | str \| None | ISO timestamp |
| month_impact | float | from the latest anomaly day |
| driver | str | latest |
| provisional | bool | latest day provisional |
| known | bool | service listed as known |

## Change
`(incident, reason)` where reason ∈ {`new`, `worse`}.

## State
`version: 1`, `incidents: list[Incident]`.
