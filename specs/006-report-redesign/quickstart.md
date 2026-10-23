# Quickstart: validate the redesigned report

```sh
uv run pytest -q
uv run python demo/run_demo.py --end-date 2026-10-15 --pdf
open demo/demo_anomalies_report.html demo/demo_anomalies_report.pdf
```

Check in the browser:

1. Top bar stays visible; nav links jump to sections without hiding headings.
2. "Giao diện tối/sáng" toggles theme, charts recolor; reload keeps the choice.
3. Filter by kind/service/labels; count "x / y dòng"; sort by clicking headers; "Xóa lọc" resets.
4. "Xuất PDF" opens print preview: light theme, no top bar/filters, all rows, nothing split.
5. Narrow window to ~360 px: no horizontal page scroll.

Failure paths (tests cover these): `--pdf --no-report` → exit 2; `COST_ANOMALY_BROWSER=/nope`
with `--pdf` → exit 2 before the MFA prompt.
