# Contract: CLI `--pdf` and HTML report

## CLI

| Input | Result |
|-------|--------|
| `--pdf` | after CSV/HTML/MD, writes `<stem>_report.pdf`; prints `PDF → <path>` |
| `--pdf --no-report` | argparse error, exit 2, no AWS call |
| `--pdf`, no browser found | stderr `error: --pdf cần Chrome, Chromium hoặc Edge ... COST_ANOMALY_BROWSER ...`, exit 2 before MFA prompt, no CSV |
| `--pdf`, rendering fails | CSV/HTML/MD kept, stderr `error: không tạo được PDF: ...`, alerting still runs, exit 2 (3 wins if Slack delivery failed) |
| no `--pdf` | unchanged; browser never looked up |
| env `COST_ANOMALY_BROWSER` | path to a Chromium-family executable; used first; must exist |

## HTML (`render_html`)

- Single file, no `http(s)://` resource references; `<html lang="vi">`.
- Section ids: `tong-quan`, `nhan-dinh`, `buoc-tiep-theo`*, `bieu-do`*, `vuot-muc`*, `bang`,
  `bi-loc`*, `cad`*, `cau-hinh` (*only when rendered); nav lists exactly the rendered ones.
- Controls: `#theme-toggle` (button, `aria-pressed` = dark), `#print-btn`, filter form
  `#filters` (kind checkboxes, service select, provisional/known selects, clear button), sortable
  `th[data-sort]` buttons with `aria-sort`.
- Embedded JSON: `<script id="report-data" type="application/json">` with `</` escaped.
