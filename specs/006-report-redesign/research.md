# Research: report redesign

## R1. CLI PDF renderer

- **Decision**: drive an installed Chromium-family browser (Chrome, Chromium, Edge) with
  `--headless --print-to-pdf` via `subprocess`. Lookup order: `$COST_ANOMALY_BROWSER`, PATH
  (`google-chrome`, `google-chrome-stable`, `chromium`, `chromium-browser`, `microsoft-edge`,
  `msedge`), then `/Applications/{Google Chrome,Chromium,Microsoft Edge}.app/...`.
- **Rationale**: charts are drawn by inline JS, so the renderer must run JS; Chrome headless
  uses the same print stylesheet as the "Xuất PDF" button, so both PDFs match (FR-021). No Python
  dependency is added (constitution VI); "optional component" = a browser on the machine.
  Flags: `--headless`, `--disable-gpu`, `--no-pdf-header-footer`, `--no-first-run`,
  `--no-default-browser-check`, `--user-data-dir=<temp>` (never touch the user's profile),
  `--print-to-pdf=<path>`, `file://` URL of the written HTML.
- **Alternatives**: Playwright (pip package + ~150 MB browser download; same engine, more
  weight); WeasyPrint (no JS → charts would need a Python SVG renderer duplicating chart code,
  plus Pango system libs). Both add dependencies the constitution asks us to avoid.

## R2. Theme without flash, persisted

- **Decision**: inline `<head>` script reads `localStorage['cost-anomaly-theme']` in try/catch and
  sets `data-theme` before first paint; with no saved value it leaves the attribute unset so the
  existing `prefers-color-scheme` tokens apply. The toggle always writes an explicit value. The
  same script adds `class="js"` to `<html>` so JS-only controls are hidden without JS (FR-032).
- **Note**: for `file://` pages, browsers may scope storage per file or per origin `null`; spec
  accepts per-file memory.

## R3. Print

- `@media print` re-declares light tokens on `:root, :root[data-theme]` (wins over dark);
  hides `.topbar`, `.js-only`; `tr`, `.chart-card`, `.stat` get `break-inside: avoid`;
  `thead { display: table-header-group }`; `.table-wrap { overflow: visible }`; filtered rows
  shown via `@media print { tr.is-hidden { display: table-row } }`; `@page { size: A4; margin: 14mm }`.
- Default order on print: `beforeprint` re-appends rows by their original index; `afterprint`
  restores the user's sort. Headless `--print-to-pdf` loads a fresh page, so it is default anyway.
- Charts: SVG gets `viewBox` already; print CSS sets `width: 100%; height: auto` so they scale to
  the page instead of the screen width.

## R4. Visual direction (frontend-design + dataviz)

- Subject: daily AWS cost anomaly report for engineers and the people they forward it to. Job:
  "is anything abnormal, how much does it cost, what do I do".
- One bold element: a **verdict headline** — a plain Vietnamese sentence with the counts and
  excess in large type, left-ruled in the severity color (critical red / DROP violet / calm
  green-gray). Everything else quiet.
- Stat strip: one bordered band split into four cells (not four floating cards); run metadata as a
  definition list, not a dot-joined string.
- Kind colors from the dataviz status palette: SPIKE critical `#d03b3b`, NEW_SERVICE serious
  `#ec835a`, DROP violet `#6250d6` light / `#9085e9` dark; shapes ● ◆ ▼ kept so color is never
  the only cue. Badges: tinted background + shape + text in ink color.
- Type: system UI stack (no network fonts allowed), scale 13/15/18/24/34, weight 650 for headings,
  tabular figures for numbers; sentence case, no all-caps labels.
