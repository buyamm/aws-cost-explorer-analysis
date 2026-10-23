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
    settled = [d for d in windows.eval_days if d not in windows.provisional_days]
    assert len(settled) == cli.MAX_EVAL_DAYS == 58


@pytest.mark.parametrize("value", ["0", "59"])
def test_eval_days_out_of_range_rejected(value, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.parse_args(["--profile", "p", "--eval-days", value])
    assert exc.value.code == 2
    assert "--eval-days must be between 1 and 58" in capsys.readouterr().err


def response_with_spike_yesterday():
    days = date_range(WINDOWS.fetch_start, WINDOWS.fetch_end)
    ec2 = {d: [98.0, 100.0, 102.0][i % 3] for i, d in enumerate(days)}
    ec2[date(2026, 10, 12)] = 150.0
    ec2[date(2026, 10, 14)] = 400.0  # T−1: not settled in Cost Explorer yet
    return {"ResultsByTime": results_from_matrix({"Amazon EC2": ec2}), "DimensionValueAttributes": []}


def run_rows(tmp_path, ce_client, *extra):
    out = tmp_path / "anomalies.csv"
    with Stubber(ce_client) as stub:
        stub.add_response("get_cost_and_usage", response_with_spike_yesterday())
        code = cli.main(["--profile", "p", "--output", str(out), "--end-date", "2026-10-15", "--no-report", *extra])
    assert code == 0
    with open(out, newline="") as f:
        return [(r["date"], r["kind"], r["provisional"]) for r in csv.DictReader(f)]


def test_spike_yesterday_is_reported_as_provisional(tmp_path, fake_session, ce_client):
    assert run_rows(tmp_path, ce_client) == [("2026-10-14", "SPIKE", "true"), ("2026-10-12", "SPIKE", "false")]


def test_no_provisional_restores_settled_window(tmp_path, fake_session, ce_client):
    assert run_rows(tmp_path, ce_client, "--no-provisional") == [("2026-10-12", "SPIKE", "false")]


def run_with_config(tmp_path, ce_client, config_text, *extra):
    cfg = tmp_path / "cost-anomaly.toml"
    cfg.write_text(config_text)
    out = tmp_path / "anomalies.csv"
    with Stubber(ce_client) as stub:
        stub.add_response("get_cost_and_usage", build_response())
        code = cli.main(
            ["--profile", "p", "--output", str(out), "--end-date", "2026-10-15", "--no-report", "--config", str(cfg), *extra]
        )
    assert code == 0
    with open(out, newline="") as f:
        return [(r["date"], r["service"]) for r in csv.DictReader(f)]


def test_config_per_service_override_applies(tmp_path, fake_session, ce_client):
    rows = run_with_config(tmp_path, ce_client, '[services."Amazon EC2"]\nmin_delta = 100\n')
    assert rows == [("2026-10-10", "Amazon Bedrock")]


def test_explicit_flag_beats_config_defaults(tmp_path, fake_session, ce_client):
    assert run_with_config(tmp_path, ce_client, "[defaults]\nk = 1000\nnew_threshold = 1000\n") == []
    rows = run_with_config(tmp_path, ce_client, "[defaults]\nk = 1000\n", "--k", "3.5")
    assert ("2026-10-12", "Amazon EC2") in rows


def test_bad_config_exits_2_before_auth(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "bad.toml"
    cfg.write_text("foo = 1\n")

    def no_auth(profile):
        raise AssertionError("must not authenticate with a bad config")

    monkeypatch.setattr(cli, "assume_role_session", no_auth)
    assert cli.main(["--profile", "p", "--config", str(cfg), "--output", str(tmp_path / "a.csv")]) == 2
    assert "foo" in capsys.readouterr().err
    assert not (tmp_path / "a.csv").exists()


def test_no_drop_flag_disables_drops(tmp_path, fake_session, ce_client):
    days = date_range(WINDOWS.fetch_start, WINDOWS.fetch_end)
    backup = {d: 40.0 for d in days}
    backup[date(2026, 10, 12)] = 0.0
    response = {"ResultsByTime": results_from_matrix({"AWS Backup": backup}), "DimensionValueAttributes": []}
    out = tmp_path / "a.csv"
    for extra, expected in (([], 1), (["--no-drop"], 0)):
        with Stubber(ce_client) as stub:
            stub.add_response("get_cost_and_usage", response)
            assert cli.main(["--profile", "p", "--output", str(out), "--end-date", "2026-10-15", "--no-report", *extra]) == 0
        with open(out, newline="") as f:
            assert len(list(csv.DictReader(f))) == expected
