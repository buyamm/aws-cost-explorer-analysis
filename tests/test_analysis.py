from datetime import date, datetime, timezone

from cost_anomaly.analysis import build_report, near_miss, runs_of
from cost_anomaly.config import Settings
from cost_anomaly.dates import compute_windows, date_range
from cost_anomaly.detect import NEW_SERVICE, SPIKE, detect, score
from cost_anomaly.html_report import render_html
from cost_anomaly.md_report import render_markdown

TODAY = date(2026, 10, 15)
SETTINGS = Settings()
WINDOWS = compute_windows(TODAY, SETTINGS)
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
