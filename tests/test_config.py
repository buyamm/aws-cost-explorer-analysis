from cost_anomaly.config import Settings


def test_provisional_days_and_driver_tolerance_defaults():
    s = Settings()
    assert s.include_provisional is True
    assert s.driver_tolerance == 0.25
