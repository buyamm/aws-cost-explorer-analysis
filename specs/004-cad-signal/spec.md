# Feature Specification: AWS Cost Anomaly Detection as a second signal

**Feature Branch**: `004-cad-signal`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "Research direction 10: add ce:GetAnomalies to the session policy and allowlist; show AWS CAD's anomalies next to the tool's results. Opt-in because the API price is unknown."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cross-check with AWS's own detector (Priority: P1)

An engineer has AWS Cost Anomaly Detection enabled (free, ML-based, a black box). They want each
run to also fetch CAD's anomalies for the same period and see, side by side: what both detected,
what only the tool detected, and what only CAD detected.

**Why this priority**: Two independent detectors agreeing raises confidence; disagreements show
blind spots of each (CAD: gradual increases, new services' first 10 days; tool: no seasonality).

**Independent Test**: With a stubbed CAD response containing one anomaly on EC2 matching a tool
spike and one on S3 the tool did not flag, the CSV marks the EC2 row `cad_match=true` and the
report lists S3 under "chỉ CAD".

**Acceptance Scenarios**:

1. **Given** `--with-cad`, **When** the run fetches data, **Then** the session may call only cost
   and usage plus get-anomalies, and nothing else, under both protection layers.
2. **Given** no `--with-cad`, **Then** permissions are exactly as before (cost and usage only).
3. **Given** a tool anomaly on service S, day d, and a CAD anomaly whose root causes include S and
   whose period covers d, **Then** the row is marked as matched.
4. **Given** CAD anomalies that match no tool anomaly, **Then** the report lists them with dates,
   services and impact.
5. **Given** CAD cannot be read (no permission, no monitor, API error), **Then** the run still
   succeeds with the tool's results, prints a warning, and the report says CAD was unavailable.
6. **Given** an incident that CAD also detected, **Then** its Slack line notes "AWS CAD cũng phát
   hiện".

### Edge Cases

- CAD anomaly still open (no end date): treated as lasting to the end of the fetch window.
- CAD anomaly without root causes: its monitored dimension value is used as the service.
- CAD results are paginated: follow tokens up to the page cap.
- Without `--with-cad`, CSV `cad_match` is empty (unknown), not `false`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `--with-cad` MUST add `ce:GetAnomalies` to the session policy and the client
  allowlist; without it both MUST stay exactly cost-and-usage only.
- **FR-002**: The tool MUST fetch CAD anomalies ending within the evaluated period, paginating
  with the existing page cap.
- **FR-003**: Each tool anomaly MUST get `cad_match` (true/false with CAD; empty without).
- **FR-004**: Reports MUST include a "Đối chiếu AWS CAD" section: counts of both / only tool /
  only CAD, and a table of CAD-only anomalies (dates, services, total impact, score).
- **FR-005**: CAD failures MUST NOT fail the run; they produce a warning and an "unavailable" note.
- **FR-006**: Slack lines MUST note when AWS CAD also detected the incident.
- **FR-007**: README MUST state that GetAnomalies pricing is not documented and how to check it
  (Cost Explorer API line on the next day's bill).
- **FR-008**: README, CLAUDE.md and the demo (with stubbed CAD response) MUST be updated.

### Key Entities

- **CAD anomaly**: id, start, end (optional), services, total impact, max score.

## Success Criteria *(mandatory)*

- **SC-001**: Permission tests prove the extra operation appears only with `--with-cad`.
- **SC-002**: In the demo, matched / tool-only / CAD-only buckets are all non-empty and correct.
- **SC-003**: A CAD access-denied error leaves the exit code and CSV identical to a run without
  `--with-cad` (`cad_match` stays empty because CAD is unavailable).

## Assumptions

- At most ~1 extra request per run (CAD returns few anomalies); cost is unknown and documented.
- Matching is by service name and date only (CAD root causes use the same SERVICE names).
