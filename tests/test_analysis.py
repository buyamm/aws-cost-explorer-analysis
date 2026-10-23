from datetime import date, datetime, timezone

from cost_anomaly.analysis import COLUMNS, build_report, near_miss, runs_of
from cost_anomaly.config import Settings
from cost_anomaly.dates import compute_windows, date_range
from cost_anomaly.detect import NEW_SERVICE, SPIKE, detect, score
from cost_anomaly.html_report import render_html
from cost_anomaly.md_report import render_markdown

TODAY = date(2026, 10, 15)
SETTINGS = Settings()
WINDOWS = compute_windows(TODAY, Settings(include_provisional=False))  # settled days only
DAYS = date_range(WINDOWS.fetch_start, WINDOWS.fetch_end)
GENERATED = datetime(2026, 10, 15, 8, 0, tzinfo=timezone.utc)


def series(cycle, overrides=None):
    s = {d: cycle[i % len(cycle)] for i, d in enumerate(DAYS)}
    s.update(overrides or {})
    return s


def report_for(matrix):
    anomalies = detect(matrix, WINDOWS.eval_days, SETTINGS)
    return build_report(matrix, WINDOWS, SETTINGS, anomalies, "demo", GENERATED)


MATRIX = {
    "EC2": series([98, 100, 102], {date(2026, 10, 9): 300, date(2026, 10, 10): 280}),
    "Bedrock": series([0.0], {d: 40.0 for d in WINDOWS.eval_days[-2:]}),
    "Lambda": series([0.9, 1.0, 1.1], {date(2026, 10, 8): 6.0}),
}


def test_runs_of_groups_consecutive_days():
    days = [date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 9)]
    assert runs_of(days) == [(date(2026, 10, 6), date(2026, 10, 7)), (date(2026, 10, 9), date(2026, 10, 9))]


def test_rollups_ordered_by_excess_with_runs_and_ongoing():
    r = report_for(MATRIX)
    ec2, bedrock = r.rollups
    assert ec2.service == "EC2" and ec2.kinds == [SPIKE]
    assert ec2.runs == [(date(2026, 10, 9), date(2026, 10, 10))]
    assert ec2.excess == 380 and not ec2.ongoing
    assert bedrock.kinds == [NEW_SERVICE] and bedrock.ongoing
    assert r.excess == 460 and r.spike_count == 2 and r.new_count == 2


def test_rows_follow_csv_order_and_explain_numbers():
    r = report_for(MATRIX)
    assert [(x.anomaly.date, x.anomaly.service) for x in r.rows] == [
        (date(2026, 10, 12), "Bedrock"),
        (date(2026, 10, 11), "Bedrock"),
        (date(2026, 10, 10), "EC2"),
        (date(2026, 10, 9), "EC2"),
    ]
    spike = r.rows[3]
    assert "$300.00" in spike.explanation and "1.4826 × MAD $2.00" in spike.explanation
    assert spike.severity == "rất mạnh"  # z ≈ 67 ≥ 4k
    assert "Không có chi phí nào" in r.rows[1].explanation


def test_flat_baseline_explains_scale_floor():
    r = report_for({"S3": series([50.0], {date(2026, 10, 12): 70.0})})
    assert "mức sàn $0.50" in r.rows[0].explanation


def test_insights_cover_overview_runs_and_new_service():
    text = "\n".join(report_for(MATRIX).insights)
    assert "Phát hiện 4 bất thường (2 SPIKE, 2 NEW_SERVICE)" in text
    assert "EC2: bất thường kéo dài 2 ngày liên tiếp" in text
    assert "Ngày 2026-10-11 chi phí đã về $" in text and "nhất thời" in text
    assert "Bedrock: chi phí mới xuất hiện" in text and "$1,200.00/30 ngày" in text


def test_lambda_small_jump_is_reported_as_near_miss():
    (m,) = report_for(MATRIX).near_misses
    assert (m.service, m.date) == ("Lambda", date(2026, 10, 8))
    assert "min_delta" in m.reason


def test_near_miss_rules():
    s = score(series([50, 100, 150], {date(2026, 10, 12): 250}), date(2026, 10, 12), SETTINGS)
    assert "biên độ" in near_miss(s, SETTINGS)
    s = score(series([0.0], {date(2026, 10, 12): 6.0}), date(2026, 10, 12), SETTINGS)
    assert "new_threshold" in near_miss(s, SETTINGS)
    s = score(series([98, 100, 102]), date(2026, 10, 12), SETTINGS)
    assert near_miss(s, SETTINGS) is None


def test_chart_points_have_threshold_after_baseline():
    points = report_for(MATRIX).charts["EC2"]
    assert len(points) == len(DAYS)
    assert points[0].median is None and points[-1].median == 100
    assert points[-1].threshold == 100 + max(3.5 * 1.4826 * 2, 10)


def test_no_anomalies_report():
    r = report_for({"EC2": series([98, 100, 102])})
    assert r.rows == [] and r.rollups == [] and r.next_steps == []
    assert "Không phát hiện bất thường" in r.insights[0]
    assert "Không có bất thường nào" in render_html(r)
    assert "Không có bất thường nào" in render_markdown(r)


def test_html_escapes_service_names():
    evil = "</script><img src=x onerror=alert(1)>"
    html = render_html(report_for({evil: series([98, 100, 102], {date(2026, 10, 12): 300})}))
    assert "</script><img" not in html  # can't close the JSON <script> early
    assert "&lt;/script&gt;&lt;img" in html  # escaped in headings and tables


def test_markdown_escapes_pipes_and_has_sections():
    md = render_markdown(report_for({"A|B": series([98, 100, 102], {date(2026, 10, 12): 300})}))
    assert "A\\|B" in md
    for heading in ("## Nhận định chính", "## Bảng bất thường", "## Cấu hình thuật toán", "## Giải thích các cột"):
        assert heading in md


SP_DAY = date(2026, 10, 12)
SP_USAGE = {"Fargate": series([78, 80, 82])}
SP_PAID = {"Fargate": series([51, 52, 53], {d: 80 for d in DAYS if d >= SP_DAY})}


def sp_report():
    anomalies = detect(SP_USAGE, WINDOWS.eval_days, SETTINGS, amortized=SP_PAID)
    return build_report(SP_USAGE, WINDOWS, SETTINGS, anomalies, "demo", GENERATED, amortized=SP_PAID)


def test_amortized_row_is_rescored_from_the_amortized_matrix():
    (row,) = sp_report().rows
    assert row.anomaly.metric == "amortized"
    assert row.score.cost == row.anomaly.cost == 80
    assert row.score.baseline_median == 52


def test_rate_row_is_labelled_and_explained():
    (row,) = sp_report().rows
    assert row.labels == ["do giá/coverage"]
    assert "chi phí thực trả" in row.explanation and "Savings Plans/RI" in row.explanation


def test_usage_driven_row_has_no_labels():
    r = report_for(MATRIX)
    assert all(x.labels == [] for x in r.rows)


def test_ri_covered_service_is_not_a_new_service_near_miss():
    usage = {"ElastiCache": series([0.0], {SP_DAY: 6.0})}
    paid = {"ElastiCache": series([60.0])}
    r = build_report(usage, WINDOWS, SETTINGS, [], "demo", GENERATED, amortized=paid)
    (m,) = r.near_misses
    assert m.score.history_days == 30 and "Service mới" not in m.reason


def test_columns_and_params_document_new_fields():
    r = sp_report()
    assert {"metric", "driver", "provisional"} <= {c for c, _ in COLUMNS}
    assert "driver_tolerance" in {p.name for p in r.params}


def test_html_and_markdown_show_rate_badge():
    r = sp_report()
    assert "do giá/coverage" in render_html(r)
    assert "SPIKE · do giá/coverage" in render_markdown(r)


def provisional_report():
    w = compute_windows(TODAY, SETTINGS)
    matrix = {"EC2": series([98, 100, 102], {date(2026, 10, 14): 300})}
    anomalies = detect(matrix, w.eval_days, SETTINGS, provisional=frozenset(w.provisional_days))
    return build_report(matrix, w, SETTINGS, anomalies, "demo", GENERATED)


def test_provisional_row_is_labelled_tam_tinh():
    (row,) = provisional_report().rows
    assert row.labels == ["tạm tính"]
    assert "tạm tính" in render_html(provisional_report())
    assert "SPIKE · tạm tính" in render_markdown(provisional_report())


def test_insight_explains_provisional_days():
    text = "\n".join(provisional_report().insights)
    assert "2026-10-13 → 2026-10-14" in text and "tạm tính" in text


def test_insight_without_provisional_keeps_skipped_note():
    text = "\n".join(report_for(MATRIX).insights)
    assert "không được đánh giá" in text


def test_params_list_include_provisional_flag():
    params = {p.name: p for p in provisional_report().params}
    assert params["include_provisional"].flag == "--no-provisional"


OVERRIDDEN = Settings(
    service_overrides={"Lambda": {"min_delta": 3}, "RDS": {"min_delta": 5}},
    ignore=frozenset({"Tax"}),
    known=frozenset({"EC2"}),
)


def overridden_report(matrix):
    anomalies = detect(matrix, WINDOWS.eval_days, OVERRIDDEN)
    return build_report(matrix, WINDOWS, OVERRIDDEN, anomalies, "demo", GENERATED)


def test_explanation_uses_the_services_own_min_delta():
    r = overridden_report({"RDS": series([179, 180, 181], {date(2026, 10, 12): 187})})
    assert "min_delta $5.00" in r.rows[0].explanation


def test_near_misses_use_service_thresholds_and_skip_ignored():
    r = overridden_report({**MATRIX, "Tax": series([0.9, 1.0, 1.1], {date(2026, 10, 8): 6.0})})
    assert ("Lambda", date(2026, 10, 8)) in {(x.anomaly.service, x.anomaly.date) for x in r.rows}
    assert r.near_misses == []


def test_known_service_is_labelled():
    r = overridden_report(MATRIX)
    assert all("đã biết" in x.labels for x in r.rows if x.anomaly.service == "EC2")


def test_params_list_service_overrides():
    names = {p.name: p for p in overridden_report(MATRIX).params}
    assert names["RDS · min_delta"].value == "$5.00"
    assert names["RDS · min_delta"].flag == "--config"


DROP_MATRIX = {
    "Backup": series([39, 40, 41], {date(2026, 10, 11): 0.0, date(2026, 10, 12): 0.0}),
    "EC2": series([98, 100, 102], {date(2026, 10, 9): 300}),
}


def test_drop_rows_are_explained_and_excluded_from_excess():
    r = report_for(DROP_MATRIX)
    drop = next(x for x in r.rows if x.anomaly.service == "Backup")
    assert "giảm" in drop.explanation and "drop_ratio" in drop.explanation
    assert r.excess == 200 and r.drop_count == 2


def test_drop_insight_and_next_step():
    r = report_for(DROP_MATRIX)
    text = "\n".join(r.insights)
    assert "Backup: chi phí rơi về gần 0" in text
    assert any("backup" in s.lower() for s in r.next_steps)


def test_drop_near_miss():
    s = score(series([98, 100, 102], {date(2026, 10, 12): 20}), date(2026, 10, 12), SETTINGS)
    assert "giảm" in near_miss(s, SETTINGS).lower()


def test_html_and_markdown_render_drop():
    r = report_for(DROP_MATRIX)
    html = render_html(r)
    assert "mk drop" in html and "DROP" in html and "1 DROP" not in html
    assert "2 DROP" in render_markdown(r)


def test_ongoing_rollup_states_month_impact():
    r = report_for({"EC2": series([98, 100, 102], {date(2026, 10, 12): 130})})
    text = "\n".join(r.insights)
    assert "nếu tiếp diễn" in text.lower() and "$600.00" in text


def test_tables_show_month_impact():
    r = report_for({"EC2": series([98, 100, 102], {date(2026, 10, 12): 130})})
    assert "Tác động tháng" in render_html(r) and "$600.00" in render_html(r)
    assert "Tác động tháng" in render_markdown(r)


def cad_report(cad, cad_error=None):
    from cost_anomaly.cad import match

    anomalies = detect(MATRIX, WINDOWS.eval_days, SETTINGS)
    if cad is not None:
        anomalies = match(anomalies, cad, WINDOWS.eval_days[-1])
    return build_report(MATRIX, WINDOWS, SETTINGS, anomalies, "demo", GENERATED, cad=cad, cad_error=cad_error)


def test_cad_section_counts_both_tool_only_and_cad_only():
    from cost_anomaly.cad import CadAnomaly

    cad = [
        CadAnomaly("a-ec2", date(2026, 10, 9), date(2026, 10, 10), frozenset({"EC2"}), 380.0, 0.9),
        CadAnomaly("a-s3", date(2026, 10, 7), date(2026, 10, 8), frozenset({"S3"}), 14.2, 0.6),
    ]
    r = cad_report(cad)
    assert (r.cad_both, r.cad_tool_only, [c.id for c in r.cad_only]) == (2, 2, ["a-s3"])
    html, md = render_html(r), render_markdown(r)
    assert "Đối chiếu AWS CAD" in html and "S3" in html and "$14.20" in html
    assert "## Đối chiếu AWS CAD" in md


def test_cad_unavailable_is_noted():
    r = cad_report(None, cad_error="GetAnomalies failed (AccessDeniedException): no")
    assert "không lấy được" in render_html(r) and "AccessDeniedException" in render_markdown(r)


def test_no_cad_section_without_with_cad():
    assert "Đối chiếu AWS CAD" not in render_html(report_for(MATRIX))


def test_columns_document_cad_match():
    assert "cad_match" in {c for c, _ in COLUMNS}
