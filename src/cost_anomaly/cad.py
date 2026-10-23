"""AWS Cost Anomaly Detection's findings as a second signal (--with-cad)."""

from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from .detect import Anomaly
from .fetch import CostExplorerError, TooManyPages


@dataclass(frozen=True)
class CadAnomaly:
    id: str
    start: date
    end: date | None  # None while the anomaly is still open
    services: frozenset[str]
    total_impact: float
    max_score: float

    def covers(self, service: str, day: date, window_end: date) -> bool:
        return service in self.services and self.start <= day <= (self.end or window_end)


def build_request(start: date, end: date) -> dict[str, Any]:
    """CAD returns anomalies whose end date falls in [start, end] (both inclusive)."""
    return {"DateInterval": {"StartDate": start.isoformat(), "EndDate": end.isoformat()}, "MaxResults": 100}


def fetch_anomalies(client, start: date, end: date, max_pages: int = 20) -> list[CadAnomaly]:
    params = build_request(start, end)
    found: list[CadAnomaly] = []
    for _ in range(max_pages):
        try:
            response = client.get_anomalies(**params)
        except ClientError as e:
            error = e.response.get("Error", {})
            raise CostExplorerError(f"GetAnomalies failed ({error.get('Code')}): {error.get('Message')}") from e
        except BotoCoreError as e:
            raise CostExplorerError(f"GetAnomalies failed: {e}") from e

        found.extend(_parse(a) for a in response.get("Anomalies", []))
        token = response.get("NextPageToken")
        if not token:
            return found
        params = {**params, "NextPageToken": token}
    raise TooManyPages(f"GetAnomalies stopped after {max_pages} pages")


def _day(value: str) -> date:
    return date.fromisoformat(value[:10])  # accepts "2026-10-10" and "2026-10-10T00:00:00Z"


def _parse(a: dict) -> CadAnomaly:
    services = {rc["Service"] for rc in a.get("RootCauses", []) if rc.get("Service")}
    if not services and a.get("DimensionValue"):
        services = {a["DimensionValue"]}
    return CadAnomaly(
        id=a["AnomalyId"],
        start=_day(a["AnomalyStartDate"]),
        end=_day(a["AnomalyEndDate"]) if a.get("AnomalyEndDate") else None,
        services=frozenset(services),
        total_impact=float(a["Impact"].get("TotalImpact", a["Impact"]["MaxImpact"])),
        max_score=float(a["AnomalyScore"]["MaxScore"]),
    )


def match(anomalies: list[Anomaly], cad: list[CadAnomaly], window_end: date) -> list[Anomaly]:
    return [replace(a, cad_match=any(c.covers(a.service, a.date, window_end) for c in cad)) for a in anomalies]


def cad_only(anomalies: list[Anomaly], cad: list[CadAnomaly], window_end: date) -> list[CadAnomaly]:
    """CAD findings that no tool anomaly falls into."""
    return [c for c in cad if not any(c.covers(a.service, a.date, window_end) for a in anomalies)]
