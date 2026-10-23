import pytest

from cost_anomaly.config import Settings
from cost_anomaly.settings_file import ConfigError, load_config


def write(tmp_path, text: str):
    path = tmp_path / "cost-anomaly.toml"
    path.write_text(text)
    return path


def test_defaults_services_ignore_and_known(tmp_path):
    path = write(
        tmp_path,
        """
ignore = ["Tax"]
known = ["Amazon Bedrock"]

[defaults]
k = 4
drop_ratio = 0.2

[services."Amazon Relational Database Service"]
min_delta = 5
min_history = 3
""",
    )
    s = load_config(path, Settings())
    assert (s.k, s.drop_ratio, s.min_delta) == (4, 0.2, 10.0)
    assert s.service_overrides == {"Amazon Relational Database Service": {"min_delta": 5, "min_history": 3}}
    assert (s.ignore, s.known) == (frozenset({"Tax"}), frozenset({"Amazon Bedrock"}))


def test_empty_file_keeps_base(tmp_path):
    base = Settings(k=3)
    assert load_config(write(tmp_path, ""), base) == base


@pytest.mark.parametrize(
    "text, message",
    [
        ("foo = 1", "foo"),
        ("[defaults]\nlookback_days = 30", "lookback_days"),
        ('[services."RDS"]\ndriver_tolerance = 0.5', "driver_tolerance"),
        ("[defaults]\nk = 'high'", "k"),
        ("[defaults]\nmin_delta = 0", "min_delta"),
        ("[defaults]\nmin_history = 2.5", "min_history"),
        ("[defaults]\ndrop_ratio = 1", "drop_ratio"),
        ("[defaults]\nk = true", "k"),
        ('ignore = "Tax"', "ignore"),
        ("[services]\nRDS = 5", "RDS"),
        ("k = [", "TOML"),
    ],
)
def test_invalid_config_is_rejected(tmp_path, text, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, text), Settings())


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="missing.toml"):
        load_config(tmp_path / "missing.toml", Settings())
