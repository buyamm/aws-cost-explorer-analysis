# Research: 002-detection-rules

## R1. Config format
- **Decision**: TOML via stdlib `tomllib` (Python ≥ 3.11). Comments, quoted keys for service
  names with spaces, no dependency.
- **Alternatives**: JSON (no comments), YAML (needs PyYAML, violates constitution VI).

## R2. Precedence
- **Decision**: built-in defaults → `[defaults]` → explicit CLI flags → `[services.*]` for that
  service. Threshold flags get argparse default `None` so "explicit" is detectable.

## R3. DROP on which measure
- **Decision**: decide on the paid (amortized) measure and require the usage measure to agree
  (or have median 0). Table:

| Case | usage | paid | DROP? |
|------|-------|------|-------|
| Outage, uncovered | → 0 | → 0 | yes |
| Outage, SP covered | → 0 | → 0 | yes |
| Outage, fully RI covered | median 0 | → 0 | yes (figures from paid) |
| RI purchased | → 0 | −40…60% | no |
| SP purchased | flat | −30…60% | no |

## R4. Month impact
- **Decision**: `delta × ((last day of month − day).days + 1)`. Simple, explainable, matches the
  research wording "delta/ngày × số ngày còn lại".
