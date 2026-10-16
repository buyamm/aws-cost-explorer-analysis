import getpass
import json
from dataclasses import dataclass
from typing import Callable

import boto3
import botocore.session
from botocore.exceptions import BotoCoreError, ClientError

from .guard import install_guard

# Effective permissions = role policy ∩ session policy, so even an AdministratorAccess
# role yields credentials that can only read Cost Explorer.
SESSION_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Action": "ce:GetCostAndUsage", "Resource": "*"}],
}
SESSION_NAME = "cost-anomaly"
DEFAULT_DURATION = 3600


class AuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class RoleProfile:
    role_arn: str
    source_profile: str
    mfa_serial: str | None
    external_id: str | None
    duration_seconds: int


def read_role_profile(profile: str) -> RoleProfile:
    try:
        config = botocore.session.Session(profile=profile).get_scoped_config()
    except BotoCoreError as e:
        raise AuthError(str(e)) from e

    role_arn, source_profile = config.get("role_arn"), config.get("source_profile")
    if not role_arn or not source_profile:
        raise AuthError(f"profile {profile!r} must define role_arn and source_profile")
    return RoleProfile(
        role_arn=role_arn,
        source_profile=source_profile,
        mfa_serial=config.get("mfa_serial"),
        external_id=config.get("external_id"),
        duration_seconds=int(config.get("duration_seconds", DEFAULT_DURATION)),
    )


def assume_role_session(
    profile: str,
    prompt: Callable[[str], str] = getpass.getpass,
    session_factory: Callable[..., boto3.Session] = boto3.Session,
) -> boto3.Session:
    """Switch into the profile's role with a session policy limited to ce:GetCostAndUsage."""
    rp = read_role_profile(profile)
    params = {
        "RoleArn": rp.role_arn,
        "RoleSessionName": SESSION_NAME,
        "Policy": json.dumps(SESSION_POLICY),
        "DurationSeconds": rp.duration_seconds,
    }
    if rp.external_id:
        params["ExternalId"] = rp.external_id
    if rp.mfa_serial:
        params["SerialNumber"] = rp.mfa_serial
        params["TokenCode"] = prompt(f"Enter MFA code for {rp.mfa_serial}: ").strip()

    try:
        source = session_factory(profile_name=rp.source_profile)
        sts = install_guard(source.client("sts"), frozenset({"AssumeRole"}))
        creds = sts.assume_role(**params)["Credentials"]
    except ClientError as e:
        error = e.response.get("Error", {})
        raise AuthError(f"AssumeRole failed ({error.get('Code')}): {error.get('Message')}") from e
    except BotoCoreError as e:
        raise AuthError(f"AssumeRole failed: {e}") from e

    return session_factory(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )
