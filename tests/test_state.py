from datetime import date, timedelta

import pytest

from cost_anomaly.config import Settings
from cost_anomaly.detect import DROP, NEW_SERVICE, SPIKE, Anomaly
from cost_anomaly.state import NEW, WORSE, LocalFileStore, State, StateError, mark_alerted, merge

FETCH_START = date(2026, 7, 17)
SETTINGS = Settings()
NOW = "2026-10-15T08:00:00+00:00"


def anomaly(day: int, delta: float = 50.0, service: str = "EC2", kind: str = SPIKE, **kw) -> Anomaly:
    return Anomaly(date(2026, 10, day), service, kind, 100 + delta, 100, 1, 30.0, delta, month_impact=delta * 10, **kw)


def run(state: State, anomalies, settings=SETTINGS):
    return merge(state, anomalies, settings, FETCH_START)


def alerted(state: State, anomalies, settings=SETTINGS) -> State:
    state, changes = run(state, anomalies, settings)
    return mark_alerted(state, changes, NOW)


def test_new_run_is_one_new_incident():
    state, changes = run(State(), [anomaly(11), anomaly(12, 80)])
    (inc,) = state.incidents
    assert (inc.service, inc.kind, inc.start, inc.end, inc.peak_delta) == ("EC2", SPIKE, date(2026, 10, 11), date(2026, 10, 12), 80)
    assert [(c.incident.id, c.reason) for c in changes] == [("EC2|SPIKE|2026-10-11", NEW)]


def test_same_anomalies_again_change_nothing():
    first = alerted(State(), [anomaly(11), anomaly(12, 80)])
    state, changes = run(first, [anomaly(11), anomaly(12, 80)])
    assert changes == [] and state == first


def test_continuation_at_similar_level_extends_quietly():
    first = alerted(State(), [anomaly(11), anomaly(12, 80)])
    state, changes = run(first, [anomaly(12, 80), anomaly(13, 90)])
    (inc,) = state.incidents
    assert changes == [] and (inc.start, inc.end, inc.peak_delta) == (date(2026, 10, 11), date(2026, 10, 13), 90)


def test_much_larger_peak_is_worse_once():
    first = alerted(State(), [anomaly(11, 80)])
    state, changes = run(first, [anomaly(12, 130)])  # +62% and +$50 ≥ min_delta
    assert [c.reason for c in changes] == [WORSE]
    again, changes = run(mark_alerted(state, changes, NOW), [anomaly(12, 130)])
    assert changes == []


def test_growth_below_min_delta_is_not_worse():
    first = alerted(State(), [anomaly(11, 12)])
    _, changes = run(first, [anomaly(12, 20)])  # +67% but only +$8 < min_delta $10
    assert changes == []


def test_new_service_flagged_daily_is_one_incident():
    days = [anomaly(d, 40, service="Bedrock", kind=NEW_SERVICE) for d in range(6, 12)]
    state = State()
    reported = 0
    for i in range(len(days)):
        state, changes = run(state, days[: i + 1])
        reported += len(changes)
        state = mark_alerted(state, changes, NOW)
    assert reported == 1 and len(state.incidents) == 1


def test_known_service_recorded_but_never_reported():
    state, changes = run(State(), [anomaly(11, known=True)])
    assert changes == [] and state.incidents[0].known


def test_gap_day_makes_two_incidents():
    state, changes = run(State(), [anomaly(9), anomaly(11)])
    assert [(i.start, i.end) for i in state.incidents] == [(date(2026, 10, 9),) * 2, (date(2026, 10, 11),) * 2]
    assert len(changes) == 2


def test_drop_worse_compares_magnitude():
    first = alerted(State(), [anomaly(11, -20, kind=DROP)])
    _, changes = run(first, [anomaly(12, -40, kind=DROP)])
    assert [c.reason for c in changes] == [WORSE]


def test_old_incidents_are_pruned():
    old = alerted(State(), [Anomaly(FETCH_START - timedelta(days=1), "EC2", SPIKE, 150, 100, 1, 30.0, 50)])
    state, _ = run(old, [])
    assert state.incidents == ()


def test_unalerted_incident_stays_new_until_delivered():
    state, changes = run(State(), [anomaly(11)])
    state, changes = run(state, [anomaly(11)])  # delivery failed last time: not marked
    assert [c.reason for c in changes] == [NEW]


def test_missing_file_is_empty_state(tmp_path):
    assert LocalFileStore(tmp_path / "state.json").load() == State()


def test_state_round_trips_through_json(tmp_path):
    store = LocalFileStore(tmp_path / "sub" / "state.json")
    state = alerted(State(), [anomaly(11, provisional=True), anomaly(12, -30, service="Backup", kind=DROP)])
    store.save(state)
    assert store.load() == state
    assert '"version": 1' in (tmp_path / "sub" / "state.json").read_text()


@pytest.mark.parametrize("text", ["{not json", '{"version": 2, "incidents": []}', '{"version": 1, "incidents": [{"service": "x"}]}'])
def test_corrupt_or_unknown_state_is_an_error(tmp_path, text):
    path = tmp_path / "state.json"
    path.write_text(text)
    with pytest.raises(StateError, match="state.json"):
        LocalFileStore(path).load()
