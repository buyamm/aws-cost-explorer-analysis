import csv
from datetime import date
from pathlib import Path

import pytest
from botocore.stub import Stubber

from conftest import results_from_matrix
from cost_anomaly import cli
from cost_anomaly.config import Settings
from cost_anomaly.dates import compute_windows, date_range
from cost_anomaly.fetch import build_request

TODAY = date(2026, 10, 15)
WINDOWS = compute_windows(TODAY, Settings())


@pytest.fixture
def fake_session(monkeypatch, ce_client):
    created = {}

    class FakeSession:
        def client(self, service, region_name=None):
            created["service"], created["region"] = service, region_name
            return ce_client

    def fake_assume_role_session(profile):
        created["profile"] = profile
        return FakeSession()

    monkeypatch.setattr(cli, "assume_role_session", fake_assume_role_session)
    return created


def build_response():
    days = date_range(WINDOWS.fetch_start, WINDOWS.fetch_end)
    ec2 = {d: [98.0, 100.0, 102.0][i % 3] for i, d in enumerate(days)}
    ec2[date(2026, 10, 12)] = 150.0
    bedrock = {d: 0.0 for d in days}
    bedrock[date(2026, 10, 10)] = 42.0
    matrix = {"Amazon EC2": ec2, "Amazon Bedrock": bedrock}
    return {"ResultsByTime": results_from_matrix(matrix), "DimensionValueAttributes": []}


def test_end_to_end_writes_csv(tmp_path, fake_session, ce_client, capsys):
    out = tmp_path / "anomalies.csv"
    with Stubber(ce_client) as stub:
        stub.add_response(
            "get_cost_and_usage", build_response(), build_request(WINDOWS.fetch_start, WINDOWS.fetch_end)
        )
        code = cli.main(["--profile", "cost-readonly", "--output", str(out), "--end-date", "2026-10-15"])
        stub.assert_no_pending_responses()

    assert code == 0
    assert fake_session == {"profile": "cost-readonly", "service": "ce", "region": "us-east-1"}
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert [(r["date"], r["service"], r["kind"]) for r in rows] == [
        ("2026-10-12", "Amazon EC2", "SPIKE"),
        ("2026-10-10", "Amazon Bedrock", "NEW_SERVICE"),
    ]
    printed = capsys.readouterr().out
    assert "Found 2 anomalies" in printed
    html, md = tmp_path / "anomalies_report.html", tmp_path / "anomalies_report.md"
    assert f"Report → {html}, {md}" in printed
    assert "Amazon EC2" in html.read_text() and "Amazon Bedrock" in md.read_text()


def test_no_report_writes_only_csv(tmp_path, fake_session, ce_client):
    out = tmp_path / "anomalies.csv"
    with Stubber(ce_client) as stub:
        stub.add_response("get_cost_and_usage", build_response())
        code = cli.main(["--profile", "p", "--output", str(out), "--end-date", "2026-10-15", "--no-report"])

    assert code == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["anomalies.csv"]


def test_report_paths_follow_output_name():
    assert cli.report_paths(Path("out/costs.csv")) == (Path("out/costs_report.html"), Path("out/costs_report.md"))


def test_aws_error_exits_2_without_csv(tmp_path, fake_session, ce_client, capsys):
    out = tmp_path / "anomalies.csv"
    with Stubber(ce_client) as stub:
        stub.add_client_error("get_cost_and_usage", service_error_code="AccessDeniedException")
        code = cli.main(["--profile", "p", "--output", str(out), "--end-date", "2026-10-15"])

    assert code == 2
    assert not out.exists()
    assert "AccessDeniedException" in capsys.readouterr().err


def test_profile_falls_back_to_aws_profile_env(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "from-env")
    assert cli.parse_args([]).profile == "from-env"


def test_profile_required():
    with pytest.raises(SystemExit):
        cli.parse_args([])


def test_eval_days_narrows_the_evaluated_window(tmp_path, fake_session, ce_client):
    out = tmp_path / "anomalies.csv"
    with Stubber(ce_client) as stub:
        stub.add_response("get_cost_and_usage", build_response())
        code = cli.main(
            ["--profile", "p", "--output", str(out), "--end-date", "2026-10-15", "--eval-days", "2", "--no-report"]
        )

    assert code == 0
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    # Evaluates 2026-10-11..12 only, so the Bedrock day (10-10) drops out.
    assert [(r["date"], r["service"]) for r in rows] == [("2026-10-12", "Amazon EC2")]


def test_eval_days_max_fits_lookback():
    args = cli.parse_args(["--profile", "p", "--eval-days", str(cli.MAX_EVAL_DAYS)])
    windows = compute_windows(TODAY, Settings(eval_days=args.eval_days))
    assert len(windows.eval_days) == cli.MAX_EVAL_DAYS == 58


@pytest.mark.parametrize("value", ["0", "59"])
def test_eval_days_out_of_range_rejected(value, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.parse_args(["--profile", "p", "--eval-days", value])
    assert exc.value.code == 2
    assert "--eval-days must be between 1 and 58" in capsys.readouterr().err
