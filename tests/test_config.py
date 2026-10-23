from cost_anomaly.config import Settings


def test_provisional_days_and_driver_tolerance_defaults():
    s = Settings()
    assert s.include_provisional is True
    assert s.driver_tolerance == 0.25


def test_drop_defaults():
    s = Settings()
    assert (s.detect_drops, s.drop_ratio, s.drop_min_median) == (True, 0.1, 10.0)
    assert s.service_overrides == {} and s.ignore == frozenset() and s.known == frozenset()


def test_for_service_applies_only_that_services_overrides():
    s = Settings(min_delta=10, service_overrides={"RDS": {"min_delta": 5, "k": 4}})
    rds = s.for_service("RDS")
    assert (rds.min_delta, rds.k) == (5, 4)
    assert s.for_service("EC2") == s
