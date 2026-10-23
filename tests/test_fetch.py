from datetime import date

import pytest
from botocore.stub import Stubber

from conftest import load_fixture
from cost_anomaly.fetch import CostExplorerError, TooManyPages, build_request, fetch_daily_costs

START, END = date(2026, 9, 30), date(2026, 10, 3)


def test_request_shape():
    assert build_request(START, END) == {
        "TimePeriod": {"Start": "2026-09-30", "End": "2026-10-03"},
        "Granularity": "DAILY",
        "Metrics": ["UnblendedCost", "NetAmortizedCost"],
        "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
        "Filter": {
            "Dimensions": {"Key": "RECORD_TYPE", "Values": ["Usage", "SavingsPlanCoveredUsage", "DiscountedUsage"]}
        },
    }


def test_single_page(ce_client):
    with Stubber(ce_client) as stub:
        stub.add_response("get_cost_and_usage", load_fixture("ce_new_service.json"), build_request(START, END))
        results = fetch_daily_costs(ce_client, START, END)
        stub.assert_no_pending_responses()
    assert len(results) == 3


def test_follows_next_page_token(ce_client):
    params = build_request(START, END)
    with Stubber(ce_client) as stub:
        stub.add_response("get_cost_and_usage", load_fixture("ce_page1.json"), params)
        stub.add_response(
            "get_cost_and_usage", load_fixture("ce_page2.json"), {**params, "NextPageToken": "token-2"}
        )
        results = fetch_daily_costs(ce_client, START, END)
        stub.assert_no_pending_responses()
    assert [r["TimePeriod"]["Start"] for r in results] == ["2026-09-30", "2026-10-01", "2026-10-01", "2026-10-02"]


def test_stops_after_max_pages(ce_client):
    looping = {**load_fixture("ce_page1.json"), "NextPageToken": "same-token"}
    with Stubber(ce_client) as stub:
        for _ in range(3):
            stub.add_response("get_cost_and_usage", looping)
        with pytest.raises(TooManyPages):
            fetch_daily_costs(ce_client, START, END, max_pages=3)
        stub.assert_no_pending_responses()


def test_client_error_is_wrapped(ce_client):
    with Stubber(ce_client) as stub:
        stub.add_client_error(
            "get_cost_and_usage", service_error_code="AccessDeniedException", service_message="not authorized"
        )
        with pytest.raises(CostExplorerError, match="AccessDeniedException"):
            fetch_daily_costs(ce_client, START, END)
