from datetime import date

import pytest
from botocore.stub import Stubber

from conftest import load_fixture
from cost_anomaly.cad import CadAnomaly, build_request, cad_only, fetch_anomalies, match
from cost_anomaly.detect import SPIKE, Anomaly
from cost_anomaly.fetch import CostExplorerError, TooManyPages

START, END = date(2026, 10, 6), date(2026, 10, 14)
EC2 = "Amazon Elastic Compute Cloud - Compute"


def test_request_shape():
    assert build_request(START, END) == {
        "DateInterval": {"StartDate": "2026-10-06", "EndDate": "2026-10-14"},
        "MaxResults": 100,
    }


def test_fetch_parses_and_paginates(ce_client):
    with Stubber(ce_client) as stub:
        stub.add_response("get_anomalies", load_fixture("ce_anomalies.json"), build_request(START, END))
        stub.add_response(
            "get_anomalies", load_fixture("ce_anomalies_page2.json"), {**build_request(START, END), "NextPageToken": "page-2"}
        )
        found = fetch_anomalies(ce_client, START, END)
        stub.assert_no_pending_responses()
    ec2, s3, cache = found
    assert ec2 == CadAnomaly("a-ec2", date(2026, 10, 11), date(2026, 10, 11), frozenset({EC2}), 228.9, 0.92)
    assert s3.services == {"Amazon Simple Storage Service"} and s3.end == date(2026, 10, 10)
    assert (cache.start, cache.end, cache.services) == (date(2026, 10, 10), None, {"Amazon ElastiCache"})


def test_fetch_stops_at_page_cap(ce_client):
    looping = {**load_fixture("ce_anomalies.json"), "NextPageToken": "again"}
    with Stubber(ce_client) as stub:
        for _ in range(2):
            stub.add_response("get_anomalies", looping)
        with pytest.raises(TooManyPages):
            fetch_anomalies(ce_client, START, END, max_pages=2)


def test_client_error_is_wrapped(ce_client):
    with Stubber(ce_client) as stub:
        stub.add_client_error("get_anomalies", service_error_code="AccessDeniedException", service_message="no")
        with pytest.raises(CostExplorerError, match="GetAnomalies.*AccessDeniedException"):
            fetch_anomalies(ce_client, START, END)


CAD = [
    CadAnomaly("a-ec2", date(2026, 10, 11), date(2026, 10, 11), frozenset({EC2}), 228.9, 0.92),
    CadAnomaly("a-cache", date(2026, 10, 10), None, frozenset({"Amazon ElastiCache"}), 380.0, 0.88),
    CadAnomaly("a-s3", date(2026, 10, 8), date(2026, 10, 10), frozenset({"Amazon Simple Storage Service"}), 14.2, 0.61),
]


def spike(service: str, day: int) -> Anomaly:
    return Anomaly(date(2026, 10, day), service, SPIKE, 150, 100, 1, 30.0, 50)


def test_match_by_service_and_period():
    matched = match([spike(EC2, 11), spike(EC2, 12), spike("Amazon ElastiCache", 14), spike("AWS Fargate", 11)], CAD, END)
    assert [a.cad_match for a in matched] == [True, False, True, False]


def test_cad_only_lists_unmatched_cad_anomalies():
    matched = match([spike(EC2, 11)], CAD, END)
    assert [c.id for c in cad_only(matched, CAD, END)] == ["a-cache", "a-s3"]
