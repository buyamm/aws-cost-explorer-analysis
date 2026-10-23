# Implementation Plan: Redesigned HTML report with light/dark theme and PDF export

**Branch**: `006-report-redesign` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

## Summary

Rewrite the presentation layer of `html_report.py` only: sticky top bar (title, section nav,
theme toggle, "Xuất PDF"), a verdict headline + stat strip instead of four identical cards, kind
badges with color + shape, a filterable/sortable anomaly table, and a print stylesheet that forces
the light theme, shows every row in CSV order and keeps rows/charts whole. The theme is set by a
tiny `<head>` script (no flash) and persisted in `localStorage` (try/catch). CLI `--pdf` prints
the written HTML to `<stem>_report.pdf` with an installed Chrome/Chromium/Edge in headless mode
through `subprocess` (new module `pdf.py`) — no new Python dependency. The browser is located
before auth; a missing browser exits 2. `analysis.py`, `md_report.py`, `report.py` and the Lambda
are unchanged.

## Technical Context

Python ≥ 3.11, stdlib only (`subprocess`, `shutil`, `tempfile`) · inline CSS/vanilla JS in the
generated HTML, no network · pytest (HTML asserted as text; subprocess faked) · manual
verification with headless Chrome screenshots/PDF of the offline demo · reports up to ~200 rows,
~30 charted services.

## Constitution Check

| Principle | Status |
|-----------|--------|
| I. Least privilege | PASS: no AWS calls added; browser lookup happens before auth |
| II. Test-first | PASS: tests per behavior before code (HTML structure, escaping, CLI flag/exit codes, pdf runner) |
| III. No real AWS | PASS: CLI tests keep fake sessions; PDF tests fake `subprocess.run`/browser lookup; conftest clears `COST_ANOMALY_BROWSER` |
| IV. API cost | PASS: no extra CE requests |
| V. Explainable | PASS: content still from `analysis.build_report`; MD/CSV untouched |
| VI. Simplicity | PASS: no new dependency — uses an already-installed browser via stdlib `subprocess` (see research R1) |
| Vietnamese UI | PASS: all new labels Vietnamese |

Re-checked after design: unchanged.

## Design

- `html_report.py`: keep `render_html(report)`/`write_html`/`chart_data`; restructure sections
  with `id`s, `nav` built from the sections actually rendered, table rows carrying `data-*`
  sort/filter keys (escaped attributes), filter controls rendered server-side inside a
  `js-only` container. JS: theme toggle, print (`window.print()`), filter/sort, `beforeprint`
  → restore default order, charts unchanged except re-render on theme change and SVG scaling
  in print.
- `pdf.py` (new): `PdfError`; `find_browser(env, which, exists) -> str` (env `COST_ANOMALY_BROWSER`,
  then PATH names, then macOS app bundles); `write_pdf(html_path, pdf_path, browser, run=subprocess.run)`
  runs headless print with a temp profile dir, 120 s timeout, checks exit code and non-empty file.
- `cli.py`: `--pdf` (argparse error with `--no-report`); locate browser in the fail-fast block
  (exit 2, Vietnamese hint); after HTML/MD, render PDF, keep the error; alerting runs; final
  exit = 3 if alert failed, else 2 if PDF failed, else as today.
- Demo: `run_demo.py` passes through `--pdf`.
- README: `--pdf`, browser requirement, exit-code note; `.gitignore` adds `*_report.pdf`.

## Project Structure

```text
src/cost_anomaly/{html_report.py (rewrite), pdf.py (new), cli.py}
tests/test_html_report.py (new), tests/test_pdf.py (new), tests/test_cli.py, tests/conftest.py
demo/run_demo.py, README.md, .gitignore
```

## Complexity Tracking

None.
