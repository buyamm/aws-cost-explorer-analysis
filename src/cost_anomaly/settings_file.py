"""Optional TOML config: default thresholds, per-service overrides, ignored and known services."""

import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Any

from .config import Settings

SERVICE_KEYS = frozenset({"k", "min_delta", "new_threshold", "min_history", "drop_ratio", "drop_min_median"})
DEFAULT_KEYS = SERVICE_KEYS | {"driver_tolerance"}
TOP_LEVEL_KEYS = frozenset({"defaults", "services", "ignore", "known"})


class ConfigError(ValueError):
    pass


def load_config(path: Path, base: Settings) -> Settings:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise ConfigError(f"cannot read config {path}: {e.strerror}") from e
    return parse_config(text, base, str(path))


def parse_config(text: str, base: Settings, source: str) -> Settings:
    """`source` (file path or variable name) appears in error messages."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"invalid TOML in {source}: {e}") from e
    try:
        return _apply(data, base)
    except ConfigError as e:
        raise ConfigError(f"{source}: {e}") from None


def _apply(data: dict, base: Settings) -> Settings:
    unknown = data.keys() - TOP_LEVEL_KEYS
    if unknown:
        raise ConfigError(f"unknown config key(s): {', '.join(sorted(unknown))}")

    defaults = _thresholds(_table(data, "defaults"), DEFAULT_KEYS, "[defaults]")
    overrides = {}
    for service, table in _table(data, "services").items():
        if not isinstance(table, dict):
            raise ConfigError(f'[services] entry {service!r} must be a table: [services."{service}"]')
        overrides[service] = _thresholds(table, SERVICE_KEYS, f'[services."{service}"]')

    return replace(
        base,
        **defaults,
        service_overrides=overrides,
        ignore=_names(data, "ignore"),
        known=_names(data, "known"),
    )


def _table(data: dict, key: str) -> dict:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ConfigError(f"{key} must be a table")
    return value


def _names(data: dict, key: str) -> frozenset[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{key} must be a list of service names")
    return frozenset(value)


def _thresholds(table: dict, allowed: frozenset[str], where: str) -> dict[str, Any]:
    unknown = table.keys() - allowed
    if unknown:
        raise ConfigError(f"{where}: unknown key(s) {', '.join(sorted(unknown))}; allowed: {', '.join(sorted(allowed))}")
    for key, value in table.items():
        # bool is an int subclass; reject it explicitly
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ConfigError(f"{where}: {key} must be a positive number")
        if key == "min_history" and not isinstance(value, int):
            raise ConfigError(f"{where}: min_history must be a whole number of days")
        if key == "drop_ratio" and value >= 1:
            raise ConfigError(f"{where}: drop_ratio must be between 0 and 1")
    return dict(table)
