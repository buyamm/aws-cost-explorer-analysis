import json
from datetime import date
from pathlib import Path

import boto3
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def results_from_matrix(matrix: dict[str, dict[date, float]]) -> list[dict]:
    """Build Cost Explorer ResultsByTime entries from {service: {day: cost}}."""
    days = sorted({d for series in matrix.values() for d in series})
    return [
        {
            "TimePeriod": {"Start": d.isoformat(), "End": date.fromordinal(d.toordinal() + 1).isoformat()},
            "Total": {},
            "Groups": [
                {"Keys": [service], "Metrics": {"UnblendedCost": {"Amount": str(series[d]), "Unit": "USD"}}}
                for service, series in sorted(matrix.items())
                if series.get(d, 0.0) > 0
            ],
            "Estimated": False,
        }
        for d in days
    ]


@pytest.fixture(autouse=True)
def fake_aws_env(monkeypatch, tmp_path):
    """Never touch real AWS credentials or config during tests."""
    for var in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN", "AWS_ROLE_ARN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "aws-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "missing-credentials"))


@pytest.fixture
def aws_config(tmp_path):
    """Path of the fake AWS config file the tests may write profiles into."""
    return tmp_path / "aws-config"


@pytest.fixture
def ce_client():
    return boto3.client("ce", region_name="us-east-1")
