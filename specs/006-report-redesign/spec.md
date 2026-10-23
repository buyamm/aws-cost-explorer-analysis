# Feature Specification: Redesigned HTML report with light/dark theme and PDF export

**Feature Branch**: `006-report-redesign`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "Làm lại trang HTML anomalies report (`<stem>_report.html`) cho dễ nhìn, có nút đổi theme Sáng/Tối và xuất PDF. Header cố định với mục lục, nút theme, nút Xuất PDF. Theme chỉ Sáng/Tối, lần đầu theo hệ điều hành, nhớ lựa chọn. PDF cách 1: nút in trên trình duyệt, bản in theme sáng, không cắt nội dung giữa trang, in mọi hàng. PDF cách 2: cờ CLI tuỳ chọn `--pdf` ghi `<stem>_report.pdf`, chỉ CLI, dependency tuỳ chọn, thiếu thì exit 2 trước xác thực. Bảng bất thường lọc theo loại/service/nhãn và sắp xếp theo cột. Làm mới tile KPI, badge, phân cấp chữ. Giữ nguyên: HTML một file tự chứa, offline, nội dung từ build_report, Markdown/CSV không đổi, tiếng Việt, escape dữ liệu không tin cậy, Lambda không cần dependency PDF, accessibility, tooltip chart và phím ←/→."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the report at a glance (Priority: P1)

An engineer opens `anomalies_report.html` after a run. A header stays visible while scrolling,
showing the report title, the data/evaluation window, a table of contents linking to every
section, and the theme and PDF buttons. KPI tiles at the top make the severity obvious (for
example, the tile is visually emphasized when there are anomalies, neutral when there are
none), and each anomaly kind has a distinct colored badge that matches its chart marker.

**Why this priority**: The report is the main way people read results; today it is one long
page with weak hierarchy, so the biggest finding is hard to locate.

**Independent Test**: Render the report from synthetic data (demo or test fixture) and check
that the header, table of contents, tiles and badges are present, that every TOC link targets
an existing section, and that the page works with no network access.

**Acceptance Scenarios**:

1. **Given** a report with anomalies, **When** the user scrolls anywhere on the page, **Then**
   the header with title, TOC, theme button and PDF button stays visible.
2. **Given** the TOC, **When** the user activates an entry (mouse or keyboard), **Then** the
   page jumps to that section and the section heading is not hidden behind the header.
3. **Given** sections that are absent for this run (for example no CAD data, no near misses),
   **Then** the TOC does not list them.
4. **Given** anomalies of kinds SPIKE, NEW_SERVICE and DROP, **Then** each row badge uses that
   kind's color and shape, consistent with the chart markers and legend.
5. **Given** a run with zero anomalies, **Then** the tiles read as calm/neutral and the page
   clearly says there is nothing to act on.

---

### User Story 2 - Switch between light and dark theme (Priority: P1)

The user clicks the theme button to switch between light and dark. On first open the page
follows the operating-system preference; after the user picks a theme, the choice is
remembered the next time any report is opened in the same browser.

**Why this priority**: Explicitly requested; reports are read both in bright offices and at
night, and charts must stay legible in both.

**Independent Test**: Open the report, toggle the theme, confirm all surfaces, text, tables,
tiles and charts change colors immediately; reload and confirm the choice persists; repeat
with browser storage blocked and confirm the toggle still works for the session.

**Acceptance Scenarios**:

1. **Given** no saved choice and an OS set to dark, **When** the report opens, **Then** it
   renders dark; with an OS set to light it renders light.
2. **Given** either theme, **When** the user activates the theme button, **Then** the page,
   including already drawn charts and tooltips, switches to the other theme without reload.
3. **Given** the user chose a theme, **When** the report (or a later report) is reopened in
   the same browser, **Then** the chosen theme is used regardless of the OS preference.
4. **Given** browser storage is unavailable, **Then** the toggle still works and the page
   shows no error; the choice simply is not remembered.
5. **Given** the theme button, **Then** it is reachable by keyboard, has a Vietnamese
   accessible label, and its label/state tells which theme is active.

---

### User Story 3 - Export the report to PDF from the browser (Priority: P2)

The user clicks "Xuất PDF" in the header; the browser's print dialog opens and the user saves
a PDF to share with people who do not open HTML files (managers, finance).

**Why this priority**: Requested; sharing a PDF is common, and this path needs no install.

**Independent Test**: Open the report, trigger the PDF button (or the browser's own print
command), and inspect the print preview / saved PDF on A4.

**Acceptance Scenarios**:

1. **Given** the report in dark theme, **When** it is printed, **Then** the output uses the
   light theme.
2. **Given** printing, **Then** the header, buttons, table filters and other interactive
   controls are hidden, and the report title and run metadata appear at the top of page 1.
3. **Given** a long anomaly table, **Then** no table row, tile, card or chart is split across a
   page break, and table column headers repeat on each page the table spans.
4. **Given** the anomaly table currently filtered or sorted, **When** printing, **Then** all
   anomaly rows are printed (none hidden by the filter) in the report's default order.
5. **Given** printing via the browser menu or keyboard shortcut instead of the button,
   **Then** the result is the same as using the button.
6. **Given** charts, **Then** they fit the printed page width and remain readable.

---

### User Story 4 - Filter and sort the anomaly table (Priority: P2)

With many anomalies, the user narrows the table by kind (SPIKE / NEW_SERVICE / DROP), by
service, and by label (tạm tính / đã biết), and sorts by clicking a column header (date,
service, cost, delta, month impact, z).

**Why this priority**: Makes large reports usable; less critical than readability and theme.

**Independent Test**: Render a report with mixed kinds, services and labels; apply each
filter and each sort and verify the visible rows and their order.

**Acceptance Scenarios**:

1. **Given** the table, **When** the user selects a kind filter, **Then** only rows of the
   selected kind(s) are shown and a visible count reads "x / y dòng".
2. **Given** a service filter, **Then** only that service's rows are shown; the list of
   services offered comes from the rows in the report.
3. **Given** label filters "tạm tính" and "đã biết", **Then** the user can show only rows with,
   or hide rows with, that label.
4. **Given** combined filters that match nothing, **Then** the table shows a Vietnamese
   "no matching rows" message and a way to clear filters.
5. **Given** a sortable column header, **When** activated (mouse or Enter/Space), **Then** rows
   sort by that column, activating again reverses the order, the active column and direction
   are indicated visually and to assistive technology, and numeric columns sort numerically
   (blank z for NEW_SERVICE sorts last).
6. **Given** "Xóa lọc", **Then** all filters reset and the default order (date, delta
   descending) returns.

---

### User Story 5 - Produce a PDF file from the CLI (Priority: P3)

An engineer running the CLI passes `--pdf` and gets `anomalies_report.pdf` next to the CSV and
other reports, ready to attach to an email or ticket without opening a browser.

**Why this priority**: Useful for automation, but the browser path already covers most needs
and this one adds an optional dependency.

**Independent Test**: With the optional PDF component installed, run the offline demo or CLI
tests with `--pdf` and check a PDF exists with the expected sections; without it, check the
run stops with exit code 2 before any credential prompt or AWS call.

**Acceptance Scenarios**:

1. **Given** `--pdf` and the optional PDF component installed, **When** the run succeeds,
   **Then** `<stem>_report.pdf` is written next to the CSV, with the same content and layout
   as the browser-printed PDF (light theme, charts included, no interactive controls).
2. **Given** `--pdf` and the optional component missing, **Then** the CLI prints a Vietnamese
   message explaining how to install it and exits with code 2 before prompting for MFA or
   calling AWS; no CSV is written.
3. **Given** `--pdf` together with `--no-report`, **Then** argument parsing rejects the
   combination with exit code 2 before any AWS call.
4. **Given** no `--pdf`, **Then** behavior and outputs are exactly as today (CSV, HTML, MD),
   and the optional component is never loaded.
5. **Given** PDF rendering fails after the CSV/HTML/MD were written, **Then** those files are
   kept, the CLI reports the PDF error, and exits with code 2.
6. **Given** the scheduled Lambda run, **Then** it uploads the new HTML (and MD, CSV) and never
   requires or produces the PDF.

---

### Edge Cases

- No anomalies: tiles neutral, empty-state message, no chart section, no filters shown, TOC
  lists only sections present; printing and `--pdf` still produce a valid one-to-few page PDF.
- Many anomalies/services (e.g. 200 rows, 30 charted services): page remains responsive;
  filters and sorting respond without noticeable delay; printing paginates cleanly.
- Service names that are long or contain HTML/script characters (`<`, `>`, `&`, `"`, `</script>`):
  displayed literally everywhere (table, filters, chart titles, tooltips, TOC), never executed,
  never break layout; long names wrap.
- Browser storage blocked or throwing (private mode, file:// restrictions): theme still toggles.
- JavaScript disabled: all text content (tiles, insights, tables, explanations, config) is still
  readable; only charts, theme toggle, filters and sorting are unavailable.
- Narrow phone-width screen (≈360 px): header collapses gracefully (TOC scrollable or in a menu),
  no horizontal page scroll; wide tables scroll inside their own container.
- Printing while dark theme active or filters applied: see User Story 3.
- Theme switched while a chart tooltip is open: tooltip updates or closes, no stale colors.
- Provisional and known labels on the same row: both labels shown and filterable.
- CAD section in error state ("không lấy được"): still listed in TOC and printed.

## Requirements *(mandatory)*

### Functional Requirements

**Layout and readability**

- **FR-001**: The HTML report MUST show a header that stays visible while scrolling, containing
  the report title, a table of contents for the sections present in this run, a theme toggle,
  and an "Xuất PDF" button.
- **FR-002**: TOC entries MUST navigate to their sections without the section heading being
  covered by the header, and MUST be keyboard operable.
- **FR-003**: KPI tiles MUST visually reflect severity: emphasized when anomalies exist (with
  stronger emphasis for SPIKE/NEW_SERVICE excess than for DROP), neutral when none exist.
- **FR-004**: Each anomaly kind (SPIKE, NEW_SERVICE, DROP) MUST have one color and one shape used
  consistently across table badges, chart markers, legend and tooltips; color MUST NOT be the
  only distinguishing cue.
- **FR-005**: Typography and spacing MUST establish a clear hierarchy (title > section headings >
  card headings > body > secondary text), and numeric columns MUST be right-aligned with tabular
  figures.
- **FR-006**: The report MUST keep all current sections and their content (key insights, next
  steps, charts, excess bars, anomaly table with explanations, near misses, CAD comparison,
  algorithm configuration, formula, column glossary).

**Theme**

- **FR-007**: The report MUST offer exactly two themes, light and dark, switchable by a single
  toggle without reloading.
- **FR-008**: With no saved choice, the initial theme MUST follow the operating-system
  preference; there MUST be no visible flash of the wrong theme on load.
- **FR-009**: A user's explicit choice MUST be remembered in the browser and applied to any
  report opened later in the same browser; if storage is unavailable the toggle MUST still work
  and no error may be shown.
- **FR-010**: Switching theme MUST immediately restyle every element, including charts already
  drawn and any open tooltip.
- **FR-011**: Both themes MUST meet WCAG 2.1 AA contrast for text (4.5:1 normal, 3:1 large) and
  3:1 for chart lines, markers and UI controls against their background.

**PDF export — browser**

- **FR-012**: The "Xuất PDF" button MUST open the browser's print dialog.
- **FR-013**: The print output MUST use the light theme, hide the header, buttons, filters and
  other interactive controls, and show the title and run metadata at the top of the first page.
- **FR-014**: The print output MUST avoid splitting tiles, cards, charts and table rows across
  pages, and MUST repeat table column headers on each page.
- **FR-015**: The print output MUST include every anomaly row in default order, regardless of
  on-screen filters or sorting.
- **FR-016**: The print output MUST be the same whether triggered by the button or the browser's
  own print command, and MUST target A4 portrait by default with charts fitting the page width.

**Anomaly table interaction**

- **FR-017**: Users MUST be able to filter anomaly rows by kind, by service, and by the labels
  "tạm tính" and "đã biết"; filters combine with AND, and a visible count shows matching versus
  total rows.
- **FR-018**: Users MUST be able to sort by date, service, kind, cost, median, z, delta and
  month impact by activating the column header; repeated activation toggles direction; the
  current sort is indicated visually and to assistive technology.
- **FR-019**: Users MUST be able to clear all filters and sorting in one action, restoring the
  default order (date, then delta, descending — same as the CSV).
- **FR-020**: When no rows match, the table MUST show a Vietnamese empty-state message.

**PDF export — CLI**

- **FR-021**: The CLI MUST accept an optional `--pdf` flag that, after a successful run, writes
  `<output stem>_report.pdf` next to the CSV with the same content as the browser print output.
- **FR-022**: The component needed to render the PDF MUST be optional: installing the tool
  without it MUST keep today's behavior, and it MUST be loaded only when `--pdf` is given.
- **FR-023**: If `--pdf` is given and the optional component is missing, the CLI MUST exit with
  code 2 and a Vietnamese installation hint before any credential prompt or AWS request.
- **FR-024**: `--pdf` combined with `--no-report` MUST be rejected at argument parsing (exit 2).
- **FR-025**: If PDF rendering fails after the other outputs were written, the CLI MUST keep
  those outputs, print the error and exit with code 2; alerting MUST still run before that exit
  so a PDF failure never suppresses an alert.
- **FR-026**: The scheduled Lambda run MUST NOT require the PDF component and MUST keep uploading
  CSV, HTML and Markdown as today.

**Preserved guarantees**

- **FR-027**: The HTML report MUST remain a single self-contained file: no network requests (no
  external fonts, scripts, styles or images), viewable offline from disk.
- **FR-028**: All report content MUST still derive from the single report model built from the
  detection results, so explanations, thresholds and charts cannot drift from what was flagged;
  the Markdown report and CSV output MUST NOT change.
- **FR-029**: All user-facing text in the HTML and PDF MUST be Vietnamese.
- **FR-030**: Service names and other untrusted strings MUST be escaped wherever they appear
  (HTML, embedded data, filters, tooltips, TOC) so they can never inject markup or script.
- **FR-031**: All controls (TOC, theme toggle, PDF button, filters, sort headers, charts) MUST
  be keyboard operable with visible focus and Vietnamese accessible names; charts MUST keep the
  hover/focus tooltip and ←/→ day navigation.
- **FR-032**: Without JavaScript, all textual content MUST remain readable.
- **FR-033**: At phone width (≈360 px) the page MUST have no horizontal page scroll.

### Key Entities

- **Report**: the existing report model (rows, rollups, charts, near misses, CAD comparison,
  params, insights, next steps); the single source for HTML, Markdown and PDF.
- **Theme preference**: light or dark, per browser; absent means "follow OS".
- **Table view state**: active filters (kinds, service, labels) and sort (column, direction);
  on-screen only, never affects print or exported PDF.
- **PDF report**: `<stem>_report.pdf`, a print rendering of the HTML report in light theme.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reader can identify the service with the largest excess cost and its date in
  under 10 seconds of opening the report.
- **SC-002**: Opening the HTML report triggers zero network requests.
- **SC-003**: Switching theme takes one click and completes visually in under 0.5 seconds,
  with 100% of text and chart elements meeting the contrast targets in FR-011.
- **SC-004**: A report with 200 anomaly rows prints to A4 with 0 rows, tiles or charts split
  across pages and column headers on every table page.
- **SC-005**: Applying a filter or sort on a 200-row table updates the view in under 0.2 seconds.
- **SC-006**: With `--pdf` and the component missing, 100% of runs exit with code 2 before any
  credential prompt or AWS request (verified by tests that fail on any AWS call).
- **SC-007**: CSV and Markdown outputs for the same input are byte-identical before and after
  this feature.
- **SC-008**: Every existing report test and the offline demo still pass; all controls are
  reachable and operable with keyboard only.

## Assumptions

- Readers use a current desktop browser (Chrome, Edge, Firefox, Safari) or a phone browser; old
  browsers without modern CSS are out of scope.
- The theme preference is shared by all reports opened in the same browser where the browser
  allows it; for reports opened from local files, some browsers isolate storage per file, in
  which case the choice is remembered per file. This is acceptable.
- The browser PDF uses the reader's print dialog; exact page breaks may differ slightly between
  browsers, but the FR-013–FR-016 guarantees hold in the supported browsers.
- The CLI PDF is rendered from the same HTML so both PDFs match; the choice of rendering
  component (a headless browser able to run the chart script, or server-side chart rendering
  with a print-to-PDF library) is deferred to `/speckit-plan`. Because the constitution limits
  runtime dependencies to the standard library plus boto3, the plan MUST justify it and keep it
  an optional extra not installed by default.
- `--pdf` is CLI-only; adding PDF upload to the Lambda is out of scope.
- No new report content or detection logic is added; this is presentation only.
- Implementation will follow the `frontend-design` skill (anthropics/skills, installed
  globally) for visual direction and the bundled `dataviz` skill for charts, palette, tiles and
  light/dark color tokens.
