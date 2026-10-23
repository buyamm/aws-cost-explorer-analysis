# Data model

No change to `analysis.Report` or any persisted format. New, presentation-only state:

| Entity | Where | Fields / rules |
|--------|-------|----------------|
| Theme preference | `localStorage['cost-anomaly-theme']` | `"light"` \| `"dark"`; absent → follow OS; read/write wrapped in try/catch |
| Table row keys | `data-*` on each anomaly `<tr>` | `idx` (CSV order), `date`, `service`, `kind`, `cost`, `median`, `z` (empty for NEW_SERVICE), `delta`, `impact`, `provisional` (`1`/`0`), `known` (`1`/`0`); attribute-escaped |
| Table view state | JS memory only | kinds ⊆ {SPIKE, NEW_SERVICE, DROP}; service (`""` = all); provisional/known ∈ {all, only, hide}; sort `(column, asc/desc)` or default (`idx`) |
| PDF output | `<output stem>_report.pdf` next to CSV | written only with `--pdf`; from the written HTML |
