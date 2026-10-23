# Feature Specification: Per-service thresholds, drop alerts and month impact

**Feature Branch**: `002-detection-rules`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "Research directions 9, 12, 8. (9) Per-service thresholds from a config file (e.g. Bedrock $50/day, RDS $5/day), plus lists of ignored and 'known' services. (12) Alert when a stable service suddenly falls to near zero (backup stopped, prod down). (8) Estimate month impact: delta/day × days left in the month → 'if this continues, +$X this month', used to rank urgency."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Thresholds that fit each service (Priority: P1)

An engineer finds the single `--min-delta $10` too noisy for Bedrock (spiky, expensive) and too
lax for RDS (steady, where +$5/day matters). They write a small config file giving Bedrock and
RDS their own thresholds, list services to ignore entirely, and mark services whose changes are
already known (still reported, clearly marked).

**Why this priority**: AWS CAD only offers one threshold per subscription; per-service tuning is
the cheapest way to cut noise without missing real issues.

**Independent Test**: With a config giving RDS `min_delta = 5`, a +$7 RDS spike is reported while
the same +$7 on a service without override is not.

**Acceptance Scenarios**:

1. **Given** a config with `[services."Amazon Relational Database Service"] min_delta = 5`,
   **When** RDS rises $7 above its baseline with a high robust z, **Then** it is reported.
2. **Given** `ignore = ["Tax"]`, **When** Tax spikes, **Then** nothing is reported for Tax and it
   does not appear in near misses.
3. **Given** `known = ["Amazon Bedrock"]`, **When** Bedrock spikes, **Then** the row is reported
   and marked known.
4. **Given** a config `[defaults] k = 4`, **When** the engineer also passes `--k 3`, **Then** the
   command-line value wins.
5. **Given** a config with an unknown key or a malformed file, **When** the tool starts, **Then**
   it exits with code 2 and a clear message before any AWS call.

---

### User Story 2 - Alert when a service stops (Priority: P2)

An engineer wants to know when a steady service suddenly falls to near zero: backups stopped,
a production workload went down, a pipeline died. Neither AWS CAD nor the tool reports this today.

**Why this priority**: Catches outages and silent failures, a gap in both tools.

**Independent Test**: A service steady at $100/day that drops to $3 on one day is reported as a
drop; a service whose cost falls 40% because a Savings Plan was purchased is not.

**Acceptance Scenarios**:

1. **Given** a service with a steady baseline ≥ the drop floor, **When** what is paid and its
   usage both fall to ≤ 10% of their medians, **Then** a DROP anomaly is reported with a negative
   delta.
2. **Given** a Reserved Instance or Savings Plan is purchased (usage measure falls but what is
   paid only falls partially, or the reverse), **Then** no DROP is reported.
3. **Given** a cheap service (median below the drop floor), **When** it falls to zero, **Then** no
   DROP is reported.
4. **Given** `--no-drop`, **Then** DROP is never reported.

---

### User Story 3 - Know how much it costs if it continues (Priority: P3)

For each anomaly the engineer sees "if this continues, +$X by the end of the month", so they can
rank what to look at first.

**Why this priority**: Turns per-day deltas into a number managers understand; enables urgency
ranking in alerts (later feature).

**Independent Test**: A +$30/day spike on 2026-10-12 shows a month impact of $600 (20 days from
the 12th to the 31st inclusive).

**Acceptance Scenarios**:

1. **Given** an anomaly with delta D on day d, **Then** month impact = D × (days from d to the last
   day of d's month, inclusive).
2. **Given** a DROP, **Then** month impact is negative (money no longer spent, or lost output).
3. **Given** a service still anomalous on the latest evaluated day, **Then** the report states the
   month impact in its insight text.

### Edge Cases

- A configured service never appears in the data: no error; the report lists the override anyway.
- A service is both ignored and known: ignore wins.
- Override values must be positive numbers (`min_history` a positive integer); otherwise exit 2.
- A day in a month's last day: month impact = delta × 1.
- DROP and the excess total: drops never reduce the "excess above normal" total.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST accept an optional config file (`--config`) that can set default
  thresholds, per-service thresholds (`k`, `min_delta`, `new_threshold`, `min_history`,
  `drop_ratio`, `drop_min_median`), a list of ignored services and a list of known services.
- **FR-002**: Explicit command-line flags MUST override config defaults; per-service values MUST
  override both for that service.
- **FR-003**: Invalid config (unknown key, wrong type, non-positive value, unreadable file) MUST
  stop the run with exit code 2 before any AWS call.
- **FR-004**: Detection, near misses, charts and explanations MUST use the per-service thresholds,
  so the report never contradicts what was flagged.
- **FR-005**: Ignored services MUST be excluded from anomalies and near misses; known services MUST
  be reported with a `known` flag.
- **FR-006**: The tool MUST report a DROP when the service has enough history, its paid median is
  at least `drop_min_median` (default $10), the paid amount fell to ≤ `drop_ratio` (default 10%)
  of its median with robust z < −k, and the usage measure fell the same way (or the usage measure
  has no baseline, as for fully RI-covered services).
- **FR-007**: `--no-drop` MUST disable DROP detection.
- **FR-008**: Each anomaly MUST carry a month impact = delta × days remaining in its month
  (inclusive); CSV gains `month_impact` and `known` columns after the existing ones.
- **FR-009**: Reports MUST show DROP with its own marker and Vietnamese explanation, a "đã biết"
  label for known services, month impact per row and in insights for ongoing anomalies, and list
  config overrides in the configuration table.
- **FR-010**: README, CLAUDE.md, and the demo (with a config file, a DROP scenario and a known
  service) MUST be updated.

### Key Entities

- **Config file**: defaults, per-service overrides, ignore list, known list.
- **Anomaly** (additions): kind may be `DROP`; `month_impact`; `known`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A per-service override changes the outcome for that service only (verified on a
  scenario with two services and the same change).
- **SC-002**: In the demo, the planted outage is reported as DROP and the planted RI/SP changes
  produce 0 DROP rows.
- **SC-003**: 100% of anomaly rows show a month impact.
- **SC-004**: A bad config never causes a billable request.

## Assumptions

- Config format is TOML (readable, comments allowed, parser in the standard library).
- DROP is evaluated on what is paid, cross-checked with the usage measure, so commitment purchases
  do not look like outages.
- Month impact uses the anomaly day's own delta; no forecasting model.
- Ranking alerts by month impact happens in the alerting feature (003); the report keeps sorting
  rollups by total excess.
