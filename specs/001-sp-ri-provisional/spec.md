# Feature Specification: Savings Plans/RI-aware data and provisional recent days

**Feature Branch**: `001-sp-ri-provisional`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "Data correctness and evaluation window for cost-anomaly (research directions 3 and 2). (3) Savings Plans / Reserved Instances: include covered usage, request amortized cost in the same request, detect on usage and amortized cost, label each anomaly usage-driven or rate-driven. (2) Daily runs with provisional days: also evaluate T-2 and T-1 labelled 'tạm tính', with a flag to restore the old behaviour. CSV gains provisional and driver columns; reports show the labels in Vietnamese. Extract the pipeline into a reusable run(). No extra Cost Explorer requests, still only ce:GetCostAndUsage, tests with Stubber only."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No fake spikes when Savings Plans or RIs change (Priority: P1)

An engineer runs the tool on an account whose compute is partly covered by Savings Plans or
Reserved Instances. Today, covered usage is invisible to the tool, so when a commitment expires
or the organization re-allocates coverage, usage "appears" and the tool reports a spike that is
not a real increase in consumption. After this feature, covered usage is counted, and when the
amount actually paid changes because of coverage or price (not consumption), the anomaly is
labelled as rate-driven so the engineer knows to look at commitments rather than workloads.

**Why this priority**: False spikes erode trust in every other alert; this is a correctness bug
in the data the whole tool depends on (risk 1 in the research).

**Independent Test**: Feed a synthetic account where usage is flat but Savings Plan coverage
ends on one day; the tool must not report a usage-driven spike, and must report a rate-driven
anomaly for the actual cost increase.

**Acceptance Scenarios**:

1. **Given** a service with flat consumption whose Savings Plan coverage ends on day D,
   **When** the tool evaluates day D, **Then** no usage-driven anomaly is reported for that
   service on D, and if the amount actually paid jumped past the thresholds a single anomaly
   labelled rate-driven is reported.
2. **Given** a service whose consumption doubles on day D with no coverage change,
   **When** the tool evaluates day D, **Then** one anomaly labelled usage-driven is reported,
   exactly as before this feature.
3. **Given** any run, **When** the tool fetches data, **Then** it makes the same number of
   billable Cost Explorer requests as before for the same date range and pagination.

---

### User Story 2 - See yesterday's costs in a daily run (Priority: P2)

An engineer wants to run the tool every day and learn about a runaway resource within about a
day instead of 3–7 days. The tool now also evaluates the two most recent days, whose data is
still settling, and labels those results "tạm tính" (provisional) so the engineer knows the
numbers may still move.

**Why this priority**: Latency is the biggest gap versus AWS Cost Anomaly Detection; it matters
once results are trustworthy (P1).

**Independent Test**: Run against a fixed end date with a planted spike on the day before the
end date; the spike appears in the output labelled provisional.

**Acceptance Scenarios**:

1. **Given** a spike on T−1, **When** the tool runs with default settings on day T,
   **Then** the spike is reported and marked provisional.
2. **Given** a spike on T−3, **When** the tool runs on day T, **Then** it is reported and not
   marked provisional.
3. **Given** the engineer passes the option to disable provisional days, **When** the tool runs,
   **Then** the evaluated days and results are identical to the behaviour before this feature
   (aside from the new columns).
4. **Given** `--eval-days N`, **When** provisional days are enabled, **Then** N settled days plus
   the provisional days are evaluated.

---

### User Story 3 - Reuse the analysis outside the CLI (Priority: P3)

A maintainer preparing an unattended scheduled run needs to invoke the full fetch → detect
pipeline with an already-authenticated session, without the interactive CLI, argument parsing
or file writing.

**Why this priority**: Enabler for later features (scheduled run); no direct user value alone.

**Independent Test**: Call the pipeline entry point with a stubbed session and settings and get
the same anomalies the CLI writes for the same data.

**Acceptance Scenarios**:

1. **Given** a session whose Cost Explorer client is stubbed, **When** the pipeline is invoked
   programmatically, **Then** it returns the cost data, evaluated days and anomalies without
   prompting or writing files.

---

### Edge Cases

- A service is fully covered by Reserved Instances, so its usage measure reads zero while its
  amortized cost is non-zero: it is not a "new service", and when the RI expires the jump is
  labelled rate-driven.
- A service has no amortized cost history but has usage cost (or the reverse): detection on the
  measure with history still works; the other measure is treated as zero.
- The same service and day is anomalous on both measures: exactly one anomaly row is reported.
- A provisional day later settles to a different value: the tool does not remember earlier runs
  (state is out of scope here); each run reflects the data it fetched.
- Cost Explorer returns a day split across pages: amounts for both measures are summed per
  service and day.
- New services (not enough history) continue to be judged on the usage measure only, so a new
  service is never reported twice.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST include usage covered by Savings Plans and Reserved Instances in the
  data it analyses, in addition to on-demand usage.
- **FR-002**: The tool MUST obtain, for every service and day, both a usage measure (cost of
  consumption at undiscounted rates where the billing data provides it) and an amortized measure
  (what was effectively paid after commitments), using a single request per page — the number of
  billable requests MUST NOT increase.
- **FR-003**: The tool MUST evaluate each service and day on the usage measure (existing rules,
  including new-service detection) and on the amortized measure (spike rule only).
- **FR-004**: Each reported anomaly MUST carry a driver label: *usage-driven* when both measures
  rose above their baselines by similar amounts (extra consumption shows up equally in what it
  would cost and what was paid), otherwise *rate-driven*. The tolerance MUST be a named setting
  with a documented default.
- **FR-005**: When a service and day is anomalous on both measures, the tool MUST report one
  anomaly, using the usage measure's figures; when only the amortized measure is anomalous, the
  anomaly MUST use the amortized figures and state which measure it is based on.
- **FR-006**: By default the tool MUST evaluate the configured number of settled days plus the
  most recent provisional days (default 2), and MUST mark results on those days as provisional.
- **FR-007**: The tool MUST provide an option that disables provisional days and restores the
  previous evaluation window.
- **FR-008**: The CSV output MUST add columns for the measure used, the driver label and the
  provisional flag; existing columns keep their names and order.
- **FR-009**: The HTML and Markdown reports MUST show the driver and provisional labels in
  Vietnamese, with an explanation of what rate-driven and "tạm tính" mean, and MUST derive them
  from the same scoring used for detection.
- **FR-010**: The fetch → transform → detect pipeline MUST be callable programmatically with a
  pre-authenticated session, returning results without prompting or writing files; the CLI MUST
  use this same entry point.
- **FR-011**: The tool MUST continue to use only the Cost Explorer cost-and-usage read operation,
  under both the session policy and the client allowlist.
- **FR-012**: README, CLAUDE.md and the offline demo MUST be updated; the demo MUST include a
  planted Savings Plan expiry scenario and a provisional-day spike.

### Key Entities

- **Daily service cost**: for each service and day, two amounts — usage measure and amortized
  measure.
- **Anomaly**: date, service, kind (spike / new service), figures (cost, baseline median, MAD,
  robust z, delta), measure used (usage / amortized), driver (usage / rate), provisional flag.
- **Evaluation window**: settled days (count configurable) plus provisional days (count
  configurable, can be disabled).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the planted Savings Plan expiry scenario, 0 usage-driven anomalies are reported
  for the affected service, and the real cost increase is reported once as rate-driven.
- **SC-002**: In a daily run, a spike that happened yesterday is visible in that run's output
  (detection latency ≤ 1 day after the cost occurs, versus 3–7 days before).
- **SC-003**: Billable requests per run are unchanged for the same date range (1–2 requests for
  typical accounts).
- **SC-004**: With provisional days disabled, the set of (date, service, kind) results on the
  existing test scenarios is identical to before the feature.
- **SC-005**: Every anomaly row in CSV and reports shows its driver and provisional status.

## Assumptions

- Savings Plan covered usage is reported at on-demand-equivalent cost; Reserved-Instance covered
  usage has zero usage cost (its charge sits in the RI fee). Verified in research.md; the driver
  rule compares absolute increases so both cases behave.
- Provisional is decided by recency only (most recent N days). Cost Explorer's per-period
  "estimated" flag is not used, because it may cover the whole open month and would label almost
  every day provisional; to be confirmed during planning.
- Commitment fees for unused Savings Plans/RIs (recurring fee records) stay out of scope: the
  tool tracks per-service consumption, not commitment utilization.
- Default tolerance for the driver label: the amortized increase is within ±25% of the usage
  increase.
- Remembering previous runs, deduplicating alerts and sending notifications are out of scope
  (later features).
