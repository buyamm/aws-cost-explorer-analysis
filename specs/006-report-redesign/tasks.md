# Tasks: Redesigned HTML report with light/dark theme and PDF export

**Tests**: REQUIRED (constitution II: red before green). HTML behavior is asserted on the rendered
text; browser-only behavior (theme switch, filters, print layout) is checked manually with
headless Chrome screenshots/PDF of the demo (T012).

- [X] T001 Baseline `uv run pytest -q`; add `COST_ANOMALY_BROWSER` removal to the autouse fixture in `tests/conftest.py`; add `*_report.pdf` to `.gitignore`

## User Story 1 — Read at a glance (P1)

- [X] T002 [US1] Failing tests `tests/test_html_report.py`: sticky `header.topbar` with title, `#theme-toggle`, `#print-btn`; nav lists exactly the rendered section ids (`tong-quan`, `nhan-dinh`, `bang`, `cau-hinh` always; `bieu-do`/`vuot-muc`/`bi-loc`/`cad`/`buoc-tiep-theo` only when present); verdict headline with severity class (`alert` with SPIKE/NEW_SERVICE, `drop` with only DROP, `calm` with none); run metadata as `<dl>`; badges `badge spike|new|drop`; no `http://`/`https://` resource references; existing `tests/test_analysis.py` HTML assertions still pass
- [X] T003 [US1] Rewrite markup + CSS in `src/cost_anomaly/html_report.py` (research R4 tokens, kind colors, type scale, stat strip, phone width) until T002 passes

## User Story 2 — Theme (P1)

- [X] T004 [US2] Failing tests in `tests/test_html_report.py`: `<head>` script before `<style>` reads `localStorage` key `cost-anomaly-theme` inside try/catch and sets `data-theme` + `js` class; toggle has `aria-pressed` and Vietnamese `aria-label`; dark tokens under both `@media (prefers-color-scheme: dark)` with `:not([data-theme="light"])` and `[data-theme="dark"]`
- [X] T005 [US2] Implement head script, toggle JS (write storage in try/catch, re-render charts, hide tooltip) in `src/cost_anomaly/html_report.py`

## User Story 3 — Browser PDF (P2)

- [X] T006 [US3] Failing tests in `tests/test_html_report.py`: `@media print` forces light tokens on `:root[data-theme="dark"]`, hides `.topbar` and `.js-only`, shows `tr.is-hidden`, `break-inside: avoid`, `thead { display: table-header-group }`, `@page` A4; `#print-btn` calls `window.print()`; `beforeprint` restores default order
- [X] T007 [US3] Implement print CSS/JS in `src/cost_anomaly/html_report.py`

## User Story 4 — Filter and sort (P2)

- [X] T008 [US4] Failing tests in `tests/test_html_report.py`: rows carry `data-idx/date/service/kind/cost/median/z/delta/impact/provisional/known` (z empty for NEW_SERVICE; service attribute-escaped for `"<>&`); `#filters` inside `.js-only` with kind checkboxes, service `<select>` options from rows (escaped, sorted, unique), provisional/known selects ("Tất cả", "Chỉ …", "Ẩn …"), "Xóa lọc", count `#row-count`; sortable headers are `<button>` in `th[data-sort]` with `aria-sort`; empty-state row "Không có dòng nào khớp bộ lọc"; filters absent when no anomalies
- [X] T009 [US4] Implement filter/sort JS (AND filters, numeric sort, empty z last, toggle direction, clear restores `idx` order) in `src/cost_anomaly/html_report.py`

## User Story 5 — CLI `--pdf` (P3)

- [X] T010 [US5] Failing tests `tests/test_pdf.py`: `find_browser` prefers `COST_ANOMALY_BROWSER` (must exist, else `PdfError`), then PATH names, then macOS app paths, else `PdfError` with Vietnamese hint; `write_pdf` calls the runner with `--headless`, `--print-to-pdf=<abs pdf>`, `--no-pdf-header-footer`, temp `--user-data-dir`, `file://` URL, timeout; non-zero exit / missing or empty file / timeout / OSError → `PdfError`. Then implement `src/cost_anomaly/pdf.py`
- [X] T011 [US5] Failing tests `tests/test_cli.py`: `--pdf --no-report` → exit 2 before auth; `--pdf` with no browser → exit 2, message mentions `COST_ANOMALY_BROWSER`, auth never called, no CSV; `--pdf` success writes via fake `write_pdf` to `<stem>_report.pdf`; render failure → CSV/HTML/MD kept, exit 2; with failing Slack → exit 3; without `--pdf` browser lookup is never called. Then implement in `src/cost_anomaly/cli.py` (`report_paths` unchanged; new `pdf_path`)

## Polish

- [X] T012 Pass `--pdf` through `demo/run_demo.py`; run the demo with real headless Chrome; screenshot light/dark/phone width and inspect PDF; fix layout issues found
- [X] T013 README (Vietnamese): report features, `--pdf`, browser requirement, `COST_ANOMALY_BROWSER`, exit code 2 note; CLAUDE.md Output section
- [X] T014 Validation: `uv run pytest -q`, demo, CSV/MD unchanged vs `main` for the demo input (SC-007)

## Dependencies

T001 → T002–T003 (US1 markup is the base for all) → US2, US3, US4 in any order (same file, so
sequential) → US5 (independent of US2–US4; T010 before T011) → Polish. MVP: T001–T005.
