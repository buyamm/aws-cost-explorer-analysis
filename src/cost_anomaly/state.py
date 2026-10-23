"""Incidents remembered across runs, so each one is reported once (and again only if it gets worse)."""

import json
from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta
from pathlib import Path

from botocore.exceptions import ClientError

from .config import Settings
from .dates import runs_of
from .detect import Anomaly

VERSION = 1
NEW = "new"
WORSE = "worse"
WORSE_RATIO = 1.5  # peak must grow by 50% (and by at least min_delta) to be reported again


@dataclass(frozen=True)
class Incident:
    """Consecutive anomalous days of one service and kind."""

    service: str
    kind: str
    start: date
    end: date
    peak_delta: float  # largest magnitude seen; negative for DROP
    month_impact: float  # from the latest day
    driver: str
    provisional: bool
    known: bool
    last_alerted_peak: float | None = None  # None: never reported
    alerted_at: str | None = None
    cad_match: bool = False  # AWS Cost Anomaly Detection also flagged one of its days

    @property
    def id(self) -> str:
        return f"{self.service}|{self.kind}|{self.start.isoformat()}"


@dataclass(frozen=True)
class State:
    incidents: tuple[Incident, ...] = ()


class StateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Change:
    incident: Incident
    reason: str  # NEW or WORSE


def merge(state: State, anomalies: list[Anomaly], settings: Settings, fetch_start: date) -> tuple[State, list[Change]]:
    """Fold this run's anomalies into the incidents; return what should be reported."""
    incidents = [i for i in state.incidents if i.end >= fetch_start]

    by_key: dict[tuple[str, str], list[Anomaly]] = {}
    for a in anomalies:
        by_key.setdefault((a.service, a.kind), []).append(a)

    for (service, kind), items in sorted(by_key.items()):
        for start, end in runs_of([a.date for a in items]):
            in_run = [a for a in items if start <= a.date <= end]
            incident = _from_run(in_run, start, end)
            touching = [
                i for i in incidents
                if (i.service, i.kind) == (service, kind)
                and start <= i.end + timedelta(days=1)
                and end >= i.start - timedelta(days=1)
            ]
            for old in touching:
                incidents.remove(old)
                incident = _combine(old, incident)
            incidents.append(incident)

    incidents.sort(key=lambda i: (i.start, i.service, i.kind))
    changes = [Change(i, reason) for i in incidents if (reason := _reason(i, settings))]
    return State(tuple(incidents)), changes


def mark_alerted(state: State, changes: list[Change], alerted_at: str) -> State:
    reported = {c.incident.id for c in changes}
    return State(
        tuple(
            replace(i, last_alerted_peak=i.peak_delta, alerted_at=alerted_at) if i.id in reported else i
            for i in state.incidents
        )
    )


def _from_run(items: list[Anomaly], start: date, end: date) -> Incident:
    peak = max(items, key=lambda a: abs(a.delta))
    latest = max(items, key=lambda a: a.date)
    return Incident(
        service=latest.service,
        kind=latest.kind,
        start=start,
        end=end,
        peak_delta=peak.delta,
        month_impact=latest.month_impact,
        driver=latest.driver,
        provisional=latest.provisional,
        known=latest.known,
        cad_match=any(a.cad_match for a in items),
    )


def _combine(old: Incident, new: Incident) -> Incident:
    """Keep the old incident's identity and alert history; take the latest day's details."""
    latest = new if new.end >= old.end else old
    return replace(
        old,
        start=min(old.start, new.start),
        end=max(old.end, new.end),
        peak_delta=max(old.peak_delta, new.peak_delta, key=abs),
        month_impact=latest.month_impact,
        driver=latest.driver,
        provisional=latest.provisional,
        known=new.known,
        cad_match=old.cad_match or new.cad_match,
    )


def _reason(i: Incident, settings: Settings) -> str | None:
    if i.known:
        return None
    if i.last_alerted_peak is None:
        return NEW
    peak, before = abs(i.peak_delta), abs(i.last_alerted_peak)
    if peak >= WORSE_RATIO * before and peak - before >= settings.for_service(i.service).min_delta:
        return WORSE
    return None


def dumps(state: State) -> str:
    incidents = [{"id": i.id, **asdict(i), "start": i.start.isoformat(), "end": i.end.isoformat()} for i in state.incidents]
    return json.dumps({"version": VERSION, "incidents": incidents}, ensure_ascii=False, indent=2) + "\n"


def loads(text: str, source: str) -> State:
    """Parse a state document; `source` names it in errors. Never silently resets (that would re-send everything)."""
    try:
        data = json.loads(text)
        if data.get("version") != VERSION:
            raise StateError(f"{source}: unsupported state version {data.get('version')!r}")
        incidents = []
        for raw in data["incidents"]:
            fields = {k: v for k, v in raw.items() if k != "id"}
            fields["start"], fields["end"] = date.fromisoformat(fields["start"]), date.fromisoformat(fields["end"])
            incidents.append(Incident(**fields))
    except StateError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise StateError(f"{source}: corrupt state file ({e})") from e
    return State(tuple(incidents))


class LocalFileStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> State:
        if not self.path.exists():
            return State()
        return loads(self.path.read_text(encoding="utf-8"), str(self.path))

    def save(self, state: State) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(dumps(state), encoding="utf-8")
        tmp.replace(self.path)  # atomic: a crash never leaves half a state file


class S3StateStore:
    """Same JSON document in S3 (scheduled runs). Needs only s3:GetObject and s3:PutObject on the key."""

    def __init__(self, client, bucket: str, key: str):
        self.client, self.bucket, self.key = client, bucket, key
        self.uri = f"s3://{bucket}/{key}"

    def load(self) -> State:
        try:
            body = self.client.get_object(Bucket=self.bucket, Key=self.key)["Body"].read()
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404"):
                return State()
            raise StateError(f"cannot read {self.uri} ({code})") from e
        return loads(body.decode("utf-8"), self.uri)

    def save(self, state: State) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=self.key, Body=dumps(state).encode("utf-8"), ContentType="application/json"
        )
