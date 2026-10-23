# Data Model: 004-cad-signal

## CadAnomaly
| Field | Type |
|-------|------|
| id | str |
| start | date |
| end | date \| None (open) |
| services | frozenset[str] |
| total_impact | float |
| max_score | float |

## Additions
- `Anomaly.cad_match: bool | None` (None = CAD not requested/unavailable)
- `Incident.cad_match: bool` (default False; optional in state JSON)
- `RunResult.cad: list[CadAnomaly] | None`, `RunResult.cad_error: str | None`
