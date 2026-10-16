from datetime import date

import pytest
from botocore.stub import Stubber

from conftest import load_fixture
from cost_anomaly.fetch import fetch_daily_costs
from cost_anomaly.guard import ForbiddenOperation, install_guard


def test_blocks_other_operations(ce_client):
    install_guard(ce_client)
    with Stubber(ce_client) as stub:
        with pytest.raises(ForbiddenOperation, match="GetCostForecast"):
            ce_client.get_cost_forecast(
                TimePeriod={"Start": "2026-10-01", "End": "2026-10-31"},
                Metric="UNBLENDED_COST",
                Granularity="MONTHLY",
            )
        stub.assert_no_pending_responses()


def test_allows_get_cost_and_usage(ce_client):
    install_guard(ce_client)
    with Stubber(ce_client) as stub:
        stub.add_response("get_cost_and_usage", load_fixture("ce_new_service.json"))
        results = fetch_daily_costs(ce_client, date(2026, 9, 30), date(2026, 10, 3))
    assert len(results) == 3
