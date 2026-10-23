import json
from datetime import datetime, timezone

import boto3
import pytest
from botocore.stub import Stubber

from cost_anomaly.auth import SESSION_POLICY, AuthError, assume_role_session, read_role_profile, session_policy
from cost_anomaly.guard import ALLOWED_OPERATIONS, CAD_OPERATIONS, ForbiddenOperation

ROLE_ARN = "arn:aws:iam::111111111111:role/Admin"
MFA = "arn:aws:iam::222222222222:mfa/me"


@pytest.fixture
def switch_role_profile(aws_config):
    aws_config.write_text(
        f"""[profile base]
region = us-east-1

[profile target]
source_profile = base
role_arn = {ROLE_ARN}
mfa_serial = {MFA}
"""
    )
    return "target"


@pytest.fixture
def sts_client():
    return boto3.client("sts", region_name="us-east-1")


class FakeSessionFactory:
    """Stands in for boto3.Session: first call is the source profile, second the role session."""

    def __init__(self, sts_client):
        self.sts_client = sts_client
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self

    def client(self, service):
        assert service == "sts"
        return self.sts_client


def assume_role_response():
    return {
        "Credentials": {
            "AccessKeyId": "ASIATEMP000000000000",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Expiration": datetime(2026, 10, 15, 12, tzinfo=timezone.utc),
        }
    }


def test_read_role_profile(switch_role_profile):
    rp = read_role_profile(switch_role_profile)
    assert (rp.role_arn, rp.source_profile, rp.mfa_serial, rp.duration_seconds) == (ROLE_ARN, "base", MFA, 3600)


def test_profile_without_role_is_rejected(aws_config):
    aws_config.write_text("[profile plain]\nregion = us-east-1\n")
    with pytest.raises(AuthError, match="role_arn"):
        read_role_profile("plain")


def test_unknown_profile_is_rejected():
    with pytest.raises(AuthError):
        read_role_profile("nope")


def test_assume_role_sends_session_policy_and_mfa(switch_role_profile, sts_client):
    factory = FakeSessionFactory(sts_client)
    prompts = []
    with Stubber(sts_client) as stub:
        stub.add_response(
            "assume_role",
            assume_role_response(),
            {
                "RoleArn": ROLE_ARN,
                "RoleSessionName": "cost-anomaly",
                "Policy": json.dumps(SESSION_POLICY),
                "DurationSeconds": 3600,
                "SerialNumber": MFA,
                "TokenCode": "123456",
            },
        )
        assume_role_session(switch_role_profile, prompt=lambda msg: prompts.append(msg) or " 123456\n",
                            session_factory=factory)
        stub.assert_no_pending_responses()

    assert prompts == [f"Enter MFA code for {MFA}: "]
    assert factory.calls == [
        {"profile_name": "base"},
        {
            "aws_access_key_id": "ASIATEMP000000000000",
            "aws_secret_access_key": "secret",
            "aws_session_token": "token",
        },
    ]


def test_session_policy_only_allows_cost_and_usage():
    (stmt,) = SESSION_POLICY["Statement"]
    assert stmt == {"Effect": "Allow", "Action": "ce:GetCostAndUsage", "Resource": "*"}


def test_assume_role_error_is_wrapped(switch_role_profile, sts_client):
    with Stubber(sts_client) as stub:
        stub.add_client_error("assume_role", service_error_code="AccessDenied", service_message="bad MFA")
        with pytest.raises(AuthError, match="AccessDenied"):
            assume_role_session(switch_role_profile, prompt=lambda _: "000000",
                                session_factory=FakeSessionFactory(sts_client))


def test_sts_client_is_guarded(switch_role_profile, sts_client):
    factory = FakeSessionFactory(sts_client)
    with Stubber(sts_client) as stub:
        stub.add_response("assume_role", assume_role_response())
        assume_role_session(switch_role_profile, prompt=lambda _: "123456", session_factory=factory)
        with pytest.raises(ForbiddenOperation):
            sts_client.get_caller_identity()


def test_session_policy_is_built_from_the_allowlist():
    assert session_policy(ALLOWED_OPERATIONS) == SESSION_POLICY
    (stmt,) = session_policy(CAD_OPERATIONS)["Statement"]
    assert stmt["Action"] == ["ce:GetAnomalies", "ce:GetCostAndUsage"]
    assert CAD_OPERATIONS - ALLOWED_OPERATIONS == {"GetAnomalies"}


def test_assume_role_sends_the_requested_operations(switch_role_profile, sts_client):
    with Stubber(sts_client) as stub:
        stub.add_response(
            "assume_role",
            assume_role_response(),
            {
                "RoleArn": ROLE_ARN,
                "RoleSessionName": "cost-anomaly",
                "Policy": json.dumps(session_policy(CAD_OPERATIONS)),
                "DurationSeconds": 3600,
                "SerialNumber": MFA,
                "TokenCode": "123456",
            },
        )
        assume_role_session(switch_role_profile, prompt=lambda _: "123456",
                            session_factory=FakeSessionFactory(sts_client), operations=CAD_OPERATIONS)
        stub.assert_no_pending_responses()
