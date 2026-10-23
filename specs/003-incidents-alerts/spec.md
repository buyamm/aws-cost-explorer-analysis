# Feature Specification: Incidents with state and Slack alerts

**Feature Branch**: `003-incidents-alerts`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "Research directions 5 and 1. (5) Persist what was already reported (service, day, kind) in a JSON file; group consecutive days into one incident with start/end; alert only when an incident is new or gets worse — fixes duplicate alerts from overlapping windows and NEW_SERVICE repeating daily. (1) Send alerts to a Slack incoming webhook, only for new/worse incidents, plus an optional non-zero exit code for CI."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One incident, not one alert per day (Priority: P1)

An engineer runs the tool daily. Evaluation windows overlap (7 settled days + 2 provisional), so
the same spike appears in up to 9 consecutive runs, and a new service is flagged every day for a
week. With a state file, the tool groups consecutive anomalous days of the same service and kind
into one incident and reports only incidents that are new or have clearly worsened since the
last run.

**Why this priority**: Without deduplication, any alerting channel becomes noise within days.

**Independent Test**: Run twice over overlapping windows with the same spike: the first run
reports one new incident, the second reports none; extending the spike by a much larger day
reports it once as worse.

**Acceptance Scenarios**:

1. **Given** an empty state, **When** a run finds a 2-day SPIKE on EC2, **Then** one new incident
   (start, end = those days) is recorded and reported.
2. **Given** that state, **When** the next run sees the same days again, **Then** nothing is
   reported and the incident is unchanged.
3. **Given** that state, **When** the next run sees the spike continue the following day at a
   similar level, **Then** the incident's end extends and nothing is reported.
4. **Given** that state, **When** the peak grows by at least 50% and at least the service's
   `min_delta`, **Then** the incident is reported once as worse.
5. **Given** a NEW_SERVICE flagged 6 days in a row, **Then** it is one incident reported once.
6. **Given** a known service, **Then** its incidents are recorded but never reported.
7. **Given** incidents that ended before the fetched data window, **Then** they are removed from
   the state file.

---

### User Story 2 - Get the alert in Slack (Priority: P2)

The engineer sets a Slack incoming webhook. After each run with new or worsened incidents, one
Slack message lists them in Vietnamese, most expensive first by month impact, with the labels
(tạm tính, do giá/coverage) and where the report is.

**Why this priority**: Turns the tool from "files you have to open" into an alerting system.

**Independent Test**: With the webhook set to a fake endpoint, a run with one new incident sends
exactly one HTTP POST with a JSON body naming the service; a run with no new incidents sends
nothing.

**Acceptance Scenarios**:

1. **Given** the webhook is configured and there are new/worse incidents, **When** the run ends,
   **Then** exactly one message is posted and the state records them as alerted.
2. **Given** no new/worse incidents, **Then** no message is posted.
3. **Given** Slack returns a server error or the network fails, **Then** the tool retries a few
   times, and if it still fails exits with code 3, still writes the CSV/report, and does not mark
   the incidents as alerted (they are sent next run).
4. **Given** a webhook value that is not an `https://hooks.slack.com/` URL, **Then** the tool exits
   with code 2 before any AWS call.
5. **Given** the dry-run option, **Then** the message is printed instead of sent and the state is
   not modified.
6. The webhook URL is never printed or logged, and is not accepted as a command-line argument.

---

### User Story 3 - Fail the CI job on new anomalies (Priority: P3)

The engineer runs the tool from CI or cron and wants a non-zero exit code when there is something
new to look at.

**Acceptance Scenarios**:

1. **Given** the fail option and a state file, **When** there are new/worse incidents, **Then**
   the exit code is 1.
2. **Given** the fail option without a state file, **When** there is any anomaly on a service not
   marked known, **Then** the exit code is 1.
3. **Given** delivery failed, **Then** exit code 3 takes precedence over 1.

### Edge Cases

- The state file does not exist yet: treated as empty.
- The state file is corrupt or from an unknown version: exit 2 with a clear message (never
  silently reset, which would re-send everything).
- A provisional-only day later disappears after Cost Explorer settles: the incident stays as
  recorded; no retraction message.
- DROP incidents: "worse" compares the magnitude of the (negative) delta.
- Two runs of the same kind separated by a normal day: two incidents.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: With a state file option, the tool MUST load prior incidents, merge this run's
  anomalies (consecutive days, same service and kind) into incidents, and save the result.
- **FR-002**: An incident MUST be reported when it is new, or when its peak magnitude grew by at
  least 50% and at least the service's `min_delta` since it was last reported. Known services
  MUST never be reported.
- **FR-003**: Incidents that ended before the fetch window MUST be pruned.
- **FR-004**: The state MUST be saved only after alert delivery succeeded (or no delivery was
  needed); dry-run MUST NOT modify it.
- **FR-005**: The tool MUST post one Slack message per run with new/worse incidents, sorted by
  month impact magnitude, showing service, kind, dates, peak delta/day, month impact, labels,
  new vs worse, and the report location; at most 10 incidents listed, with a count of the rest.
- **FR-006**: The webhook URL MUST come from the environment variable
  `COST_ANOMALY_SLACK_WEBHOOK`, MUST be an `https://hooks.slack.com/…` URL, and MUST never be
  printed or logged.
- **FR-007**: Delivery MUST time out (10 s), retry transient failures (network errors, HTTP 429
  and 5xx) with backoff, and exit 3 if delivery finally fails.
- **FR-008**: An option MUST make the exit code 1 when there is something new (new/worse
  incidents with state; non-known anomalies without state).
- **FR-009**: Without the state, webhook and fail options, behaviour MUST be unchanged.
- **FR-010**: README (Vietnamese), CLAUDE.md and the demo (two consecutive runs showing
  dedup, dry-run Slack payload) MUST be updated.

### Key Entities

- **Incident**: service, kind, start, end, peak delta, last alerted peak, alerted at, latest
  month impact, driver, provisional, known.
- **State file**: version, incidents.

## Success Criteria *(mandatory)*

- **SC-001**: Over 9 consecutive daily runs covering one 2-day spike, exactly 1 alert is produced.
- **SC-002**: A new service flagged 7 days in a row produces exactly 1 alert.
- **SC-003**: A failed Slack delivery loses no alert: the next successful run sends it.
- **SC-004**: No test or demo makes a real network call.

## Assumptions

- JSON file on local disk for now; the scheduled run (005) stores the same JSON in S3 through the
  same store interface.
- Without a webhook, "delivery" is a short summary printed to stdout, and the state still records
  incidents as alerted (the exit code is the alert in CI).
- Message language Vietnamese; Slack mrkdwn formatting.
