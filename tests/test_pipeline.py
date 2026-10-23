from datetime import date

import pytest
from botocore.stub import Stubber

from conftest import results_from_matrix
from cost_anomaly import pipeline
from cost_anomaly.config import Settings
from cost_anomaly.dates import compute_windows, date_range
from cost_anomaly.detect import AMORTIZED, RATE, SPIKE
from cost_anomaly.fetch import build_request
from cost_anomaly.guard import ForbiddenOperation

TODAY = date(2026, 10, 15)
SETTINGS = Settings()
WINDOWS = compute_windows(TODAY, SETTINGS)
DAYS = date_range(WINDOWS.fetch_start, WINDOWS.fetch_end)


class FakeSession:
    def __init__(self, client):
        self.client_calls = []
        self._client = client

    def client(self, service, region_name=None):
        self.client_calls.append((service, region_name))
        return self._client


def fargate_sp_expiry():
    usage = {"AWS Fargate": {d: 80.0 for d in DAYS}}  # flat on-demand-equivalent usage
    paid = {"AWS Fargate": {d: (80.0 if d >= date(2026, 10, 10) else 52.0) for d in DAYS}}
    return {"ResultsByTime": results_from_matrix(usage, paid), "DimensionValueAttributes": []}


def test_run_returns_matrices_windows_and_anomalies(tmp_path, monkeypatch, ce_client):
    monkeypatch.chdir(tmp_path)
    session = FakeSession(ce_client)
    with Stubber(ce_client) as stub:
        stub.add_response("get_cost_and_usage", fargate_sp_expiry(), build_request(WINDOWS.fetch_start, WINDOWS.fetch_end))
        result = pipeline.run(session, SETTINGS, TODAY)
        stub.assert_no_pending_responses()

    assert session.client_calls == [("ce", "us-east-1")]
    assert result.windows == WINDOWS
    assert result.usage["AWS Fargate"][date(2026, 10, 9)] == 80.0
    assert result.amortized["AWS Fargate"][date(2026, 10, 10)] == 80.0
    first = result.anomalies[0]
    assert (first.date, first.kind, first.metric, first.driver) == (date(2026, 10, 10), SPIKE, AMORTIZED, RATE)
    assert list(tmp_path.iterdir()) == []  # writes nothing


def test_run_guards_the_cost_explorer_client(ce_client):
    with Stubber(ce_client) as stub:
        stub.add_response("get_cost_and_usage", fargate_sp_expiry())
        pipeline.run(FakeSession(ce_client), SETTINGS, TODAY)
    with pytest.raises(ForbiddenOperation):
        ce_client.get_cost_forecast(
            TimePeriod={"Start": "2026-10-01", "End": "2026-10-31"}, Metric="UNBLENDED_COST", Granularity="MONTHLY"
        )
