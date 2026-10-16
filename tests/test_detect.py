from datetime import date

import pytest

from cost_anomaly.config import Settings
from cost_anomaly.dates import compute_windows, date_range
from cost_anomaly.detect import NEW_SERVICE, SPIKE, detect

TODAY = date(2026, 10, 15)
SETTINGS = Settings()
WINDOWS = compute_windows(TODAY, SETTINGS)
DAYS = date_range(WINDOWS.fetch_start, WINDOWS.fetch_end)
EVAL_DAY = date(2026, 10, 12)  # T-3


def series(cycle: list[float], overrides: dict[date, float] | None = None) -> dict[date, float]:
    s = {d: cycle[i % len(cycle)] for i, d in enumerate(DAYS)}
    s.update(overrides or {})
    return s


def run(s: dict[date, float]):
    return detect({"svc": s}, WINDOWS.eval_days, SETTINGS)


def test_clear_spike():
    (a,) = run(series([98, 100, 102], {EVAL_DAY: 130}))
    assert (a.date, a.kind, a.baseline_median) == (EVAL_DAY, SPIKE, 100)
    assert a.delta == 30
    assert a.robust_z == pytest.approx(30 / (1.4826 * 2))


def test_high_z_but_small_delta_is_ignored():
    assert run(series([0.9, 1.0, 1.1], {EVAL_DAY: 5.0})) == []


def test_large_delta_but_volatile_service_is_ignored():
    assert run(series([50, 100, 150], {EVAL_DAY: 200})) == []


def test_drop_is_ignored():
    assert run(series([98, 100, 102], {EVAL_DAY: 0})) == []


def test_flat_baseline_mad_zero():
    (a,) = run(series([5.0], {EVAL_DAY: 30.0}))
    assert a.kind == SPIKE and a.mad == 0
    assert run(series([5.0], {EVAL_DAY: 5.5})) == []


def test_new_service_above_threshold():
    (a,) = run(series([0.0], {EVAL_DAY: 50.0}))
    assert a.kind == NEW_SERVICE and a.robust_z is None


def test_new_service_below_threshold_is_ignored():
    assert run(series([0.0], {EVAL_DAY: 5.0})) == []


def test_sparse_history_treated_as_new():
    # Only 3 non-zero baseline days (< min_history=7) → NEW_SERVICE rule, not MAD
    overrides = {date(2026, 9, d): 20.0 for d in (20, 21, 22)}
    (a,) = run(series([0.0], {**overrides, EVAL_DAY: 25.0}))
    assert a.kind == NEW_SERVICE


@pytest.mark.parametrize("recent", [date(2026, 10, 13), date(2026, 10, 14)])
def test_spike_in_two_most_recent_days_is_ignored(recent):
    assert run(series([98, 100, 102], {recent: 500})) == []


def test_spike_detected_on_each_eval_day_only_once():
    s = series([98, 100, 102], {date(2026, 10, 6): 200})
    (a,) = run(s)
    assert a.date == date(2026, 10, 6)
