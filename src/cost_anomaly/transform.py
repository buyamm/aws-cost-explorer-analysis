from collections import defaultdict
from datetime import date

from .dates import date_range

CostMatrix = dict[str, dict[date, float]]


def to_matrix(results: list[dict], start: date, end: date) -> CostMatrix:
    """Pivot ResultsByTime into {service: {day: cost}} over [start, end).

    A day can be split across pages, so amounts are summed per (service, day).
    Days without a record for a service are filled with 0.0.
    """
    sums: dict[str, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for result in results:
        day = date.fromisoformat(result["TimePeriod"]["Start"])
        for group in result.get("Groups", []):
            service = group["Keys"][0]
            sums[service][day] += float(group["Metrics"]["UnblendedCost"]["Amount"])

    days = date_range(start, end)
    return {service: {d: by_day.get(d, 0.0) for d in days} for service, by_day in sums.items()}
