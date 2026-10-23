from datetime import date

import pytest

from cost_anomaly.alert import AlertError
from cost_anomaly.alerting import process
from cost_anomaly.config import Settings
from cost_anomaly.detect import SPIKE, Anomaly
from cost_anomaly.state import NEW, LocalFileStore, State

FETCH_START = date(2026, 7, 17)
NOW = "2026-10-15T08:00:00+00:00"
SPIKES = [Anomaly(date(2026, 10, 12), "EC2", SPIKE, 150, 100, 1, 30.0, 50)]


class Recorder:
    def __init__(self, fail: bool = False):
        self.calls, self.fail = [], fail

    def __call__(self, changes):
        self.calls.append(changes)
        if self.fail:
            raise AlertError("Slack returned HTTP 500")


def test_changes_are_delivered_then_saved_as_alerted(tmp_path):
    store, deliver = LocalFileStore(tmp_path / "s.json"), Recorder()
    changes = process(SPIKES, Settings(), FETCH_START, store, deliver, NOW)
    assert [c.reason for c in changes] == [NEW] and len(deliver.calls) == 1
    (inc,) = store.load().incidents
    assert inc.alerted_at == NOW and inc.last_alerted_peak == 50


def test_nothing_new_skips_delivery_but_saves(tmp_path):
    store, deliver = LocalFileStore(tmp_path / "s.json"), Recorder()
    process(SPIKES, Settings(), FETCH_START, store, deliver, NOW)
    assert process(SPIKES, Settings(), FETCH_START, store, deliver, NOW) == []
    assert len(deliver.calls) == 1


def test_failed_delivery_keeps_previous_state(tmp_path):
    store = LocalFileStore(tmp_path / "s.json")
    with pytest.raises(AlertError):
        process(SPIKES, Settings(), FETCH_START, store, Recorder(fail=True), NOW)
    assert store.load() == State()


def test_save_false_never_writes(tmp_path):
    store = LocalFileStore(tmp_path / "s.json")
    process(SPIKES, Settings(), FETCH_START, store, Recorder(), NOW, save=False)
    assert not (tmp_path / "s.json").exists()
