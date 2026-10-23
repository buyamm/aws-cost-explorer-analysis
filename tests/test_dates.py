from datetime import date

import pytest

from cost_anomaly.config import Settings
from cost_anomaly.dates import baseline_days, compute_windows, date_range

TODAY = date(2026, 10, 15)


def test_fetch_window_is_90_days_ending_yesterday():
    w = compute_windows(TODAY, Settings())
    assert w.fetch_start == date(2026, 7, 17)
    assert w.fetch_end == TODAY  # exclusive
    assert len(date_range(w.fetch_start, w.fetch_end)) == 90


def test_two_most_recent_days_are_evaluated_as_provisional():
    w = compute_windows(TODAY, Settings())
    assert w.eval_days == [date(2026, 10, d) for d in range(6, 15)]
    assert w.provisional_days == [date(2026, 10, 13), date(2026, 10, 14)]


def test_without_provisional_eval_days_skip_two_most_recent_days():
    w = compute_windows(TODAY, Settings(include_provisional=False))
    assert w.eval_days == [date(2026, 10, d) for d in range(6, 13)]
    assert w.provisional_days == []


def test_baseline_is_30_days_before_day():
    days = baseline_days(date(2026, 10, 6), 30)
    assert len(days) == 30
    assert days[0] == date(2026, 9, 6)
    assert days[-1] == date(2026, 10, 5)


def test_baseline_of_oldest_eval_day_fits_in_fetch_window():
    w = compute_windows(TODAY, Settings())
    assert baseline_days(w.eval_days[0], 30)[0] >= w.fetch_start


def test_rejects_lookback_too_short_for_baseline():
    with pytest.raises(ValueError):
        compute_windows(TODAY, Settings(lookback_days=30))
