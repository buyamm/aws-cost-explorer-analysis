from datetime import date
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError


class CostExplorerError(RuntimeError):
    pass


class TooManyPages(RuntimeError):
    pass


# Usage measure (on-demand-equivalent for Savings Plans) and what was effectively paid.
METRICS = ["UnblendedCost", "NetAmortizedCost"]
# Covered usage must be included, or SP/RI expiry shows up as a fake usage spike.
RECORD_TYPES = ["Usage", "SavingsPlanCoveredUsage", "DiscountedUsage"]


def build_request(start: date, end: date) -> dict[str, Any]:
    return {
        "TimePeriod": {"Start": start.isoformat(), "End": end.isoformat()},
        "Granularity": "DAILY",
        "Metrics": METRICS,
        "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
        "Filter": {"Dimensions": {"Key": "RECORD_TYPE", "Values": RECORD_TYPES}},
    }


def fetch_daily_costs(client, start: date, end: date, max_pages: int = 20) -> list[dict]:
    """Return all ResultsByTime entries for [start, end), following NextPageToken."""
    params = build_request(start, end)
    results: list[dict] = []
    for _ in range(max_pages):
        try:
            response = client.get_cost_and_usage(**params)
        except ClientError as e:
            error = e.response.get("Error", {})
            raise CostExplorerError(
                f"GetCostAndUsage failed ({error.get('Code')}): {error.get('Message')}"
            ) from e
        except BotoCoreError as e:
            raise CostExplorerError(f"GetCostAndUsage failed: {e}") from e

        results.extend(response.get("ResultsByTime", []))
        token = response.get("NextPageToken")
        if not token:
            return results
        params = {**params, "NextPageToken": token}

    raise TooManyPages(f"Stopped after {max_pages} pages; raise --max-pages if this is expected")
