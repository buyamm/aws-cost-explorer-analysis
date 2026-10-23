from datetime import date

import pytest

from cost_anomaly.config import Settings
from cost_anomaly.dates import compute_windows, date_range
from cost_anomaly.detect import AMORTIZED, NEW_SERVICE, RATE, SPIKE, USAGE, Score, detect, driver, score, score_pair

TODAY = date(2026, 10, 15)
SETTINGS = Settings()
WINDOWS = compute_windows(TODAY, Settings(include_provisional=False))  # settled days only
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
def test_spike_in_two_most_recent_days_is_ignored_without_provisional(recent):
    assert run(series([98, 100, 102], {recent: 500})) == []


@pytest.mark.parametrize("recent", [date(2026, 10, 13), date(2026, 10, 14)])
def test_spike_in_provisional_day_is_flagged_provisional(recent):
    w = compute_windows(TODAY, SETTINGS)
    s = series([98, 100, 102], {recent: 500})
    (a,) = detect({"svc": s}, w.eval_days, SETTINGS, provisional=frozenset(w.provisional_days))
    assert (a.date, a.kind, a.provisional) == (recent, SPIKE, True)


def test_spike_detected_on_each_eval_day_only_once():
    s = series([98, 100, 102], {date(2026, 10, 6): 200})
    (a,) = run(s)
    assert a.date == date(2026, 10, 6)


def delta_score(delta: float) -> Score:
    return Score(cost=100 + delta, baseline_median=100, mad=1, history_days=30, scale=1.4826, robust_z=delta / 1.4826, delta=delta)


def test_history_counts_presence_series_when_given():
    usage = series([0.0])  # fully RI-covered: usage measure reads zero
    paid = series([60.0])
    assert score(usage, EVAL_DAY, SETTINGS).history_days == 0
    assert score(usage, EVAL_DAY, SETTINGS, presence=paid).history_days == 30


def test_score_pair_scores_both_measures_with_shared_history():
    usage, paid = series([0.0], {EVAL_DAY: 95.0}), series([60.0], {EVAL_DAY: 95.0})
    su, sa = score_pair(usage, paid, EVAL_DAY, SETTINGS)
    assert (su.delta, sa.delta) == (95.0, 35.0)
    assert su.history_days == sa.history_days == 30


@pytest.mark.parametrize(
    "du, da, expected",
    [
        (100, 100, USAGE),  # extra uncovered consumption: same dollars in both measures
        (100, 80, USAGE),  # within ±25%
        (100, 130, RATE),
        (2, 30, RATE),  # Savings Plan expiry: usage flat, paid jumps
        (95, 35, RATE),  # RI expiry: usage 0 → 95, paid 60 → 95
        (100, -5, RATE),
        (-5, 30, RATE),
    ],
)
def test_driver_compares_absolute_increases(du, da, expected):
    assert driver(delta_score(du), delta_score(da), 0.25) == expected


def run_both(usage: dict[date, float], paid: dict[date, float]):
    return detect({"svc": usage}, WINDOWS.eval_days, SETTINGS, amortized={"svc": paid})


def test_savings_plan_expiry_is_a_rate_driven_amortized_spike():
    # Usage flat at the on-demand-equivalent $100; SP ends on EVAL_DAY so paid goes $70 → $100.
    paid = series([69, 70, 71], {d: 100 for d in DAYS if d >= EVAL_DAY})
    (a,) = run_both(series([98, 100, 102]), paid)
    assert (a.date, a.kind, a.metric, a.driver) == (EVAL_DAY, SPIKE, AMORTIZED, RATE)
    assert (a.cost, a.baseline_median, a.delta) == (100, 70, 30)


def test_consumption_spike_in_both_measures_is_one_usage_driven_row():
    (a,) = run_both(series([98, 100, 102], {EVAL_DAY: 200}), series([68, 70, 72], {EVAL_DAY: 170}))
    assert (a.kind, a.metric, a.driver) == (SPIKE, USAGE, USAGE)
    assert a.cost == 200


def test_reserved_instance_expiry_is_not_a_new_service():
    usage = series([0.0], {EVAL_DAY: 95.0})
    paid = series([59, 60, 61], {EVAL_DAY: 95.0})
    (a,) = run_both(usage, paid)
    assert (a.kind, a.metric, a.driver) == (SPIKE, USAGE, RATE)


def test_new_service_comes_from_usage_only_and_is_usage_driven():
    (a,) = run_both(series([0.0], {EVAL_DAY: 50.0}), series([0.0], {EVAL_DAY: 35.0}))
    assert (a.kind, a.metric, a.driver) == (NEW_SERVICE, USAGE, USAGE)


def test_without_amortized_matrix_results_are_usage_driven():
    (a,) = run(series([98, 100, 102], {EVAL_DAY: 130}))
    assert (a.metric, a.driver, a.provisional) == (USAGE, USAGE, False)
