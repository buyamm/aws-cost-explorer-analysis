import csv
from datetime import date

import pytest

from cost_anomaly.detect import AMORTIZED, NEW_SERVICE, RATE, SPIKE, Anomaly
from cost_anomaly.report import FIELDS, write_csv


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_header_only_when_no_anomalies(tmp_path):
    out = tmp_path / "a.csv"
    write_csv([], out)
    assert out.read_text().strip() == ",".join(FIELDS)


def test_rows_sorted_by_date_then_delta_desc(tmp_path):
    out = tmp_path / "a.csv"
    write_csv(
        [
            Anomaly(date(2026, 10, 10), "A", SPIKE, 50, 10, 1, 26.98, 40),
            Anomaly(date(2026, 10, 12), "B", SPIKE, 30, 10, 1, 13.49, 20),
            Anomaly(date(2026, 10, 12), "C", NEW_SERVICE, 99, 0, 0, None, 99),
        ],
        out,
    )
    rows = read_rows(out)
    assert [r["service"] for r in rows] == ["C", "B", "A"]
    assert rows[0]["robust_z"] == ""
    assert rows[1] == {
        "date": "2026-10-12",
        "service": "B",
        "kind": "SPIKE",
        "cost": "30.0000",
        "baseline_median": "10.0000",
        "mad": "1.0000",
        "robust_z": "13.49",
        "delta": "20.0000",
        "metric": "usage",
        "driver": "usage",
        "provisional": "false",
        "month_impact": "0.0000",
        "known": "false",
        "cad_match": "",
    }


def test_header_keeps_old_columns_first():
    assert FIELDS == [
        "date", "service", "kind", "cost", "baseline_median", "mad", "robust_z", "delta",
        "metric", "driver", "provisional", "month_impact", "known", "cad_match",
    ]


def test_rate_driven_provisional_row(tmp_path):
    out = tmp_path / "a.csv"
    write_csv([Anomaly(date(2026, 10, 14), "Fargate", SPIKE, 80, 52, 1, 18.9, 28, AMORTIZED, RATE, True)], out)
    (row,) = read_rows(out)
    assert (row["metric"], row["driver"], row["provisional"]) == ("amortized", "rate", "true")


def test_month_impact_and_known_columns(tmp_path):
    out = tmp_path / "a.csv"
    a = Anomaly(date(2026, 10, 12), "Bedrock", SPIKE, 80, 50, 1, 20.2, 30, month_impact=600, known=True)
    write_csv([a], out)
    (row,) = read_rows(out)
    assert (row["month_impact"], row["known"]) == ("600.0000", "true")


@pytest.mark.parametrize("value, text", [(True, "true"), (False, "false"), (None, "")])
def test_cad_match_column(tmp_path, value, text):
    out = tmp_path / "a.csv"
    write_csv([Anomaly(date(2026, 10, 12), "EC2", SPIKE, 80, 50, 1, 20.2, 30, cad_match=value)], out)
    assert read_rows(out)[0]["cad_match"] == text
