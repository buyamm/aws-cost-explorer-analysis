import io
import json
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

import boto3
import pytest
from botocore.stub import ANY, Stubber

from conftest import results_from_matrix
from cost_anomaly import lambda_handler
from cost_anomaly.alert import AlertError
from cost_anomaly.config import Settings
from cost_anomaly.dates import compute_windows, date_range
from cost_anomaly.fetch import build_request
from cost_anomaly.guard import ForbiddenOperation
from cost_anomaly.settings_file import ConfigError

NOW = datetime(2026, 10, 15, 2, 0, tzinfo=timezone.utc)
WINDOWS = compute_windows(NOW.date(), Settings())
WEBHOOK = "https://hooks.slack.com/services/T0/B0/SECRET"
ENV = {
    "STATE_BUCKET": "cost-bucket",
    "STATE_KEY": "state/incidents.json",
    "REPORT_PREFIX": "reports/",
    "SLACK_WEBHOOK_PARAMETER": "/cost-anomaly/slack-webhook",
    "ACCOUNT_LABEL": "project-a",
}
REPORT_KEYS = [f"reports/2026-10-15/{name}" for name in ("anomalies.csv", "anomalies_report.html", "anomalies_report.md")]


class FakeSession:
    def __init__(self, **clients):
        self.clients, self.requested = clients, []

    def client(self, service, region_name=None):
        self.requested.append(service)
        return self.clients[service]


@pytest.fixture
def clients():
    return {
        "ce": boto3.client("ce", region_name="us-east-1"),
        "s3": boto3.client("s3", region_name="us-east-1"),
        "ssm": boto3.client("ssm", region_name="us-east-1"),
    }


@pytest.fixture
def slack(monkeypatch):
    posts = []

    def urlopen(request, timeout):
        posts.append(json.loads(request.data))
        if getattr(urlopen, "fail", False):
            raise urllib.error.HTTPError(request.full_url, 500, "boom", {}, None)
        return io.BytesIO(b"ok")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr("cost_anomaly.alert.time.sleep", lambda s: None)
    urlopen.posts = posts
    return urlopen


def ce_response():
    days = date_range(WINDOWS.fetch_start, WINDOWS.fetch_end)
    ec2 = {d: [98.0, 100.0, 102.0][i % 3] for i, d in enumerate(days)}
    ec2[date(2026, 10, 12)] = 300.0
    return {"ResultsByTime": results_from_matrix({"Amazon EC2": ec2}), "DimensionValueAttributes": []}


def stub_all(stubs, *, ssm=True, state_saved=True):
    ce, s3, ssm_stub = stubs
    if ssm:
        ssm_stub.add_response(
            "get_parameter",
            {"Parameter": {"Name": ENV["SLACK_WEBHOOK_PARAMETER"], "Type": "SecureString", "Value": WEBHOOK}},
            {"Name": ENV["SLACK_WEBHOOK_PARAMETER"], "WithDecryption": True},
        )
    s3.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404,
                        expected_params={"Bucket": "cost-bucket", "Key": "state/incidents.json"})
    ce.add_response("get_cost_and_usage", ce_response(), build_request(WINDOWS.fetch_start, WINDOWS.fetch_end))
    for key in REPORT_KEYS:
        s3.add_response("put_object", {}, {"Bucket": "cost-bucket", "Key": key, "Body": ANY, "ContentType": ANY})
    if state_saved:
        s3.add_response("put_object", {}, {"Bucket": "cost-bucket", "Key": "state/incidents.json", "Body": ANY,
                                          "ContentType": "application/json"})


def run(clients, env=ENV):
    return lambda_handler.run_scheduled(env, FakeSession(**clients), NOW)


def test_scheduled_run_tracks_state_uploads_reports_and_alerts(clients, slack, caplog):
    stubs = [Stubber(clients[s]) for s in ("ce", "s3", "ssm")]
    stub_all(stubs)
    with stubs[0], stubs[1], stubs[2]:
        summary = run(clients)
        for s in stubs:
            s.assert_no_pending_responses()
    assert summary == {
        "date": "2026-10-15",
        "anomalies": 1,
        "alerted": 1,
        "cad_error": None,
        "reports": "s3://cost-bucket/reports/2026-10-15/",
    }
    (post,) = slack.posts
    assert "Amazon EC2" in json.dumps(post) and "s3://cost-bucket/reports/2026-10-15/anomalies_report.html" in json.dumps(post)
    assert "SECRET" not in caplog.text


def test_without_slack_parameter_summary_is_logged(clients, slack, caplog):
    env = {k: v for k, v in ENV.items() if k != "SLACK_WEBHOOK_PARAMETER"}
    stubs = [Stubber(clients[s]) for s in ("ce", "s3", "ssm")]
    stub_all(stubs, ssm=False)
    with stubs[0], stubs[1], stubs[2], caplog.at_level("INFO"):
        assert run(clients, env)["alerted"] == 1
    assert slack.posts == [] and "Amazon EC2" in caplog.text


def test_slack_failure_raises_and_keeps_state(clients, slack):
    slack.fail = True
    stubs = [Stubber(clients[s]) for s in ("ce", "s3", "ssm")]
    stub_all(stubs, state_saved=False)
    with stubs[0], stubs[1], stubs[2]:
        with pytest.raises(AlertError):
            run(clients)
        stubs[1].assert_no_pending_responses()


def test_invalid_config_fails_before_cost_explorer(clients):
    with Stubber(clients["ce"]) as ce:
        with pytest.raises(ConfigError, match="COST_ANOMALY_CONFIG"):
            run(clients, {**ENV, "COST_ANOMALY_CONFIG": "foo = 1"})
        ce.assert_no_pending_responses()


def test_clients_are_guarded(clients):
    session = FakeSession(**clients)
    s3 = lambda_handler.guarded_s3(session)
    with pytest.raises(ForbiddenOperation):
        s3.delete_object(Bucket="cost-bucket", Key="state/incidents.json")
    with pytest.raises(ForbiddenOperation):
        lambda_handler.guarded_ssm(session).put_parameter(Name="x", Value="y", Type="String")


def test_with_cad_env_reads_cad(clients, slack):
    stubs = [Stubber(clients[s]) for s in ("ce", "s3", "ssm")]
    ce, s3, ssm = stubs
    ssm.add_response("get_parameter", {"Parameter": {"Value": WEBHOOK}})
    s3.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404)
    ce.add_response("get_cost_and_usage", ce_response())
    ce.add_response("get_anomalies", {"Anomalies": []})
    for _ in range(4):
        s3.add_response("put_object", {})
    with ce, s3, ssm:
        assert run(clients, {**ENV, "WITH_CAD": "true"})["cad_error"] is None
        ce.assert_no_pending_responses()
