from datetime import date

from conftest import load_fixture
from cost_anomaly.transform import to_matrix

START, END = date(2026, 9, 30), date(2026, 10, 3)
EC2 = "Amazon Elastic Compute Cloud - Compute"
S3 = "Amazon Simple Storage Service"


def paged_results():
    return load_fixture("ce_page1.json")["ResultsByTime"] + load_fixture("ce_page2.json")["ResultsByTime"]


def test_sums_day_split_across_pages():
    m = to_matrix(paged_results(), START, END)
    assert m[EC2][date(2026, 10, 1)] == 12.5
    assert m[S3][date(2026, 10, 1)] == 1.0


def test_missing_days_are_zero():
    m = to_matrix(paged_results(), START, END)
    assert m[S3][date(2026, 10, 2)] == 0.0
    assert set(m[S3]) == {date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2)}


def test_new_service_backfilled_with_zero():
    m = to_matrix(load_fixture("ce_new_service.json")["ResultsByTime"], START, END)
    assert m["Amazon Bedrock"] == {date(2026, 9, 30): 0.0, date(2026, 10, 1): 0.0, date(2026, 10, 2): 42.0}
    assert m["AWS Lambda"][date(2026, 10, 1)] == 0.0
