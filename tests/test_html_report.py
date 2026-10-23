import re
from dataclasses import replace
from datetime import date, datetime, timezone

from cost_anomaly.analysis import build_report
from cost_anomaly.config import Settings
from cost_anomaly.dates import compute_windows, date_range
from cost_anomaly.detect import detect
from cost_anomaly.html_report import render_html

TODAY = date(2026, 10, 15)
SETTINGS = Settings()
WINDOWS = compute_windows(TODAY, Settings(include_provisional=False))
DAYS = date_range(WINDOWS.fetch_start, WINDOWS.fetch_end)
GENERATED = datetime(2026, 10, 15, 8, 0, tzinfo=timezone.utc)


def series(cycle, overrides=None):
    s = {d: cycle[i % len(cycle)] for i, d in enumerate(DAYS)}
    s.update(overrides or {})
    return s


def report_for(matrix, tweak=None):
    anomalies = detect(matrix, WINDOWS.eval_days, SETTINGS)
    if tweak:
        anomalies = [tweak(a) for a in anomalies]
    return build_report(matrix, WINDOWS, SETTINGS, anomalies, "demo", GENERATED)


MIXED = {
    "EC2": series([98, 100, 102], {date(2026, 10, 9): 300, date(2026, 10, 10): 280}),
    "Bedrock": series([0.0], {d: 40.0 for d in WINDOWS.eval_days[-2:]}),
    "Backup": series([39, 40, 41], {date(2026, 10, 11): 0.0, date(2026, 10, 12): 0.0}),
}
QUIET = {"EC2": series([98, 100, 102])}
DROP_ONLY = {"Backup": series([39, 40, 41], {date(2026, 10, 12): 0.0})}


def nav_ids(html):
    nav = re.search(r'<nav class="toc"[^>]*>(.*?)</nav>', html, re.S).group(1)
    return re.findall(r'href="#([^"]+)"', nav)


def anomaly_rows(html):
    tbody = re.search(r'<tbody id="anomaly-rows">(.*?)</tbody>', html, re.S).group(1)
    return re.findall(r"<tr class=\"arow\"([^>]*)>", tbody)


# --- US1: layout


def test_topbar_has_title_nav_and_controls():
    html = render_html(report_for(MIXED))
    top = re.search(r'<header class="topbar">(.*?)</header>', html, re.S).group(1)
    assert "Báo cáo chi phí AWS bất thường" in top
    assert 'id="theme-toggle"' in top and 'id="print-btn"' in top and "Xuất PDF" in top


def test_nav_lists_exactly_rendered_sections():
    html = render_html(report_for(MIXED))
    ids = nav_ids(html)
    assert ids == ["tong-quan", "nhan-dinh", "buoc-tiep-theo", "bieu-do", "vuot-muc", "bang", "cau-hinh"]
    for i in ids:
        assert f'<section id="{i}"' in html


def test_nav_skips_absent_sections():
    ids = nav_ids(render_html(report_for(QUIET)))
    assert ids == ["tong-quan", "nhan-dinh", "bang", "cau-hinh"]


def test_verdict_severity():
    assert 'class="verdict alert"' in render_html(report_for(MIXED))
    assert 'class="verdict drop"' in render_html(report_for(DROP_ONLY))
    quiet = render_html(report_for(QUIET))
    assert 'class="verdict calm"' in quiet and "Không có chi phí bất thường" in quiet


def test_verdict_states_counts_and_excess():
    html = render_html(report_for(MIXED))
    verdict = re.search(r'<p class="verdict alert">(.*?)</p>', html, re.S).group(1)
    assert "6 bất thường" in verdict and "3 service" in verdict and "$460.00" in verdict


def test_run_metadata_is_a_definition_list():
    html = render_html(report_for(MIXED))
    dl = re.search(r'<dl class="runmeta">(.*?)</dl>', html, re.S).group(1)
    assert "<dt>Profile</dt>" in dl and "2026-10-06 → 2026-10-12" in dl


def test_kind_badges_have_kind_class():
    html = render_html(report_for(MIXED))
    for kind in ("spike", "new", "drop"):
        assert f'class="badge {kind}"' in html


def test_self_contained_no_network_resources():
    html = render_html(report_for(MIXED))
    assert not re.search(r'(src|href)="https?://', html)
    assert "@import" not in html and "url(http" not in html


def test_untrusted_service_name_escaped_everywhere():
    evil = '</script><img src=x onerror=alert(1)>"'
    html = render_html(report_for({evil: series([98, 100, 102], {date(2026, 10, 12): 300})}))
    markup = re.sub(r'<script id="report-data".*?</script>', "", html, flags=re.S)  # inert JSON, "</" escaped
    assert "<img" not in markup and "</script><img" not in html
    assert 'data-service="&lt;/script&gt;&lt;img src=x onerror=alert(1)&gt;&quot;"' in html
    assert '<option value="&lt;/script&gt;&lt;img src=x onerror=alert(1)&gt;&quot;">' in html


# --- US2: theme


def test_head_script_applies_saved_theme_before_styles():
    html = render_html(report_for(MIXED))
    head = html.split("</head>")[0]
    script = re.search(r"<script>(.*?)</script>", head, re.S)
    assert script and head.index("<script>") < head.index("<style>")
    body = script.group(1)
    assert "cost-anomaly-theme" in body and "try" in body and "catch" in body
    assert "dataset.theme" in body and "classList.add('js')" in body


def test_theme_toggle_is_labelled_button():
    html = render_html(report_for(MIXED))
    button = re.search(r'<button[^>]*id="theme-toggle"[^>]*>', html).group(0)
    assert 'type="button"' in button and "aria-pressed" in button and 'aria-label="' in button


def test_dark_tokens_cover_os_and_explicit_choice():
    html = render_html(report_for(MIXED))
    assert '@media (prefers-color-scheme: dark)' in html
    assert ':root:not([data-theme="light"])' in html and ':root[data-theme="dark"]' in html


def test_theme_choice_is_persisted_with_guard():
    html = render_html(report_for(MIXED))
    assert "localStorage.setItem('cost-anomaly-theme'" in html


# --- US3: print


def print_css(html):
    return re.search(r"@media print \{(.*)\n\}\n", html, re.S).group(1)


def test_print_forces_light_and_hides_controls():
    css = print_css(render_html(report_for(MIXED)))
    assert ':root[data-theme="dark"]' in css and "--page: #ffffff" in css
    assert ".topbar" in css and ".js-only" in css and "display: none" in css


def test_print_keeps_rows_whole_and_shows_filtered_rows():
    html = render_html(report_for(MIXED))
    css = print_css(html)
    assert "break-inside: avoid" in css and "table-header-group" in css
    assert "tr.is-hidden" in css
    assert "@page" in html and "A4" in html


def test_print_button_and_default_order_on_print():
    html = render_html(report_for(MIXED))
    assert "window.print()" in html
    assert "beforeprint" in html and "afterprint" in html


# --- US4: filter and sort


def test_rows_carry_sort_and_filter_keys():
    html = render_html(report_for(MIXED, lambda a: replace(a, known=a.service == "EC2")))
    rows = anomaly_rows(html)
    assert len(rows) == 6
    first = rows[0]
    for key in ("idx", "date", "service", "kind", "cost", "median", "z", "delta", "impact", "provisional", "known"):
        assert f"data-{key}=" in first
    assert 'data-idx="0"' in first
    new_rows = [r for r in rows if 'data-kind="NEW_SERVICE"' in r]
    assert new_rows and all('data-z=""' in r for r in new_rows)
    assert all('data-known="1"' in r for r in rows if 'data-service="EC2"' in r)


def test_filters_offer_kinds_services_and_labels():
    html = render_html(report_for(MIXED, lambda a: replace(a, known=a.service == "EC2", provisional=a.service == "Bedrock")))
    filters = re.search(r'<div id="filters" class="filters js-only">(.*?)</div>\s*<div class="card table-wrap">', html, re.S).group(1)
    for kind in ("SPIKE", "NEW_SERVICE", "DROP"):
        assert f'value="{kind}" checked' in filters
    services = re.findall(r'<option value="([^"]+)">', filters)
    assert services[:3] == ["Backup", "Bedrock", "EC2"]
    assert "Chỉ tạm tính" in filters and "Ẩn tạm tính" in filters
    assert "Chỉ đã biết" in filters and "Ẩn đã biết" in filters
    assert "Xóa lọc" in filters and 'id="row-count"' in filters


def test_label_filters_only_when_labels_exist():
    html = render_html(report_for(MIXED))
    assert "Chỉ tạm tính" not in html and "Chỉ đã biết" not in html


def test_sortable_headers_are_buttons_with_aria_sort():
    html = render_html(report_for(MIXED))
    heads = re.findall(r'<th data-sort="(\w+)" aria-sort="none"(?: class="num")?><button type="button">', html)
    assert heads == ["date", "service", "kind", "cost", "median", "z", "delta", "impact"]


def test_empty_filter_state_row():
    html = render_html(report_for(MIXED))
    assert 'class="no-match" hidden' in html and "Không có dòng nào khớp bộ lọc" in html


def test_no_filters_without_anomalies():
    html = render_html(report_for(QUIET))
    assert 'id="filters"' not in html and "Không có bất thường nào" in html
