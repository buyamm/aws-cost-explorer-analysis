import csv
from datetime import date

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
    }


def test_header_keeps_old_columns_first():
    assert FIELDS == [
        "date", "service", "kind", "cost", "baseline_median", "mad", "robust_z", "delta",
        "metric", "driver", "provisional",
    ]


def test_rate_driven_provisional_row(tmp_path):
    out = tmp_path / "a.csv"
    write_csv([Anomaly(date(2026, 10, 14), "Fargate", SPIKE, 80, 52, 1, 18.9, 28, AMORTIZED, RATE, True)], out)
    (row,) = read_rows(out)
    assert (row["metric"], row["driver"], row["provisional"]) == ("amortized", "rate", "true")
