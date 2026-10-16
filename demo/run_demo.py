"""Offline demo: run the real cost-anomaly CLI against simulated AWS.

Nothing here talks to AWS. The demo writes a throwaway AWS config, answers the MFA
prompt itself, and stubs STS + Cost Explorer with botocore's Stubber, feeding 90 days
of synthetic per-service costs with a few planted scenarios.

    uv run python demo/run_demo.py [--end-date 2026-10-15] [--output demo/demo_anomalies.csv]
"""

import argparse
import csv
import json
import os
import random
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore.stub import ANY, Stubber

from cost_anomaly import auth, cli
from cost_anomaly.config import Settings
from cost_anomaly.dates import compute_windows, date_range
from cost_anomaly.fetch import build_request

PROFILE = "project-cost"
ROLE_ARN = "arn:aws:iam::111122223333:role/CostReader"
MFA_SERIAL = "arn:aws:iam::444455556666:mfa/demo-device"
FAKE_MFA = "123456"
DUMMY_KEYS = {"aws_access_key_id": "DEMO", "aws_secret_access_key": "DEMO"}


# --------------------------------------------------------------------------- data


def simulate_costs(days: list[date], eval_days: list[date], seed: int = 7) -> dict[str, dict[date, float]]:
    """Synthetic daily costs per service, with scenarios planted inside the eval window."""
    rng = random.Random(seed)
    e = eval_days  # oldest first, 7 days

    def series(base: float, noise: float, weekend: float = 1.0, trend: float = 0.0) -> dict[date, float]:
        out = {}
        for i, d in enumerate(days):
            v = (base + trend * i) * (weekend if d.weekday() >= 5 else 1.0)
            out[d] = round(max(v * (1 + rng.gauss(0, noise)), 0.0), 4)
        return out

    m = {
        "Amazon Elastic Compute Cloud - Compute": series(320, 0.03, weekend=0.85),
        "EC2 - Other": series(25, 0.05),
        "Amazon Relational Database Service": series(180, 0.01),
        "Amazon Simple Storage Service": series(40, 0.02, trend=0.17),
        "AWS Lambda": series(5, 0.08),
        "AmazonCloudWatch": series(12, 0.04),
        "Amazon Bedrock": {d: 0.0 for d in days},
    }

    # 1. EC2 compute spike (someone launched a fleet of large instances for a day)
    m["Amazon Elastic Compute Cloud - Compute"][e[5]] = 540.0
    # 2. NAT Gateway / data transfer surge for two days
    m["EC2 - Other"][e[3]] = 96.5
    m["EC2 - Other"][e[4]] = 88.2
    # 3. New service: Bedrock starts being used mid-window
    for i, d in enumerate(e[1:]):
        m["Amazon Bedrock"][d] = round(30 + 8 * i + rng.uniform(-2, 2), 4)
    # 4. Lambda doubles, but +$7 stays under --min-delta → filtered as noise
    m["AWS Lambda"][e[2]] = 12.0
    # S3 grows slowly the whole time → trend, not a spike → no alert
    return m


def to_results(matrix: dict[str, dict[date, float]], days: list[date]) -> list[dict]:
    return [
        {
            "TimePeriod": {"Start": d.isoformat(), "End": (d + timedelta(days=1)).isoformat()},
            "Total": {},
            "Groups": [
                {"Keys": [svc], "Metrics": {"UnblendedCost": {"Amount": f"{s[d]:.4f}", "Unit": "USD"}}}
                for svc, s in sorted(matrix.items())
                if s[d] > 0
            ],
            "Estimated": d >= days[-2],
        }
        for d in days
    ]


# --------------------------------------------------------------------------- fake AWS


def write_aws_config(path: Path) -> None:
    path.write_text(
        f"[profile base]\nregion = us-east-1\n\n"
        f"[profile {PROFILE}]\nsource_profile = base\nrole_arn = {ROLE_ARN}\nmfa_serial = {MFA_SERIAL}\n"
    )


class FakeSession:
    def __init__(self, client):
        self._client = client

    def client(self, service, region_name=None):
        return self._client


def install_fake_aws(results: list[dict], start: date, end: date) -> list[Stubber]:
    """Patch cli.assume_role_session so the real auth code runs against stubbed STS/CE."""
    sts = boto3.client("sts", region_name="us-east-1", **DUMMY_KEYS)
    ce = boto3.client("ce", region_name="us-east-1", **DUMMY_KEYS)
    sts_stub, ce_stub = Stubber(sts), Stubber(ce)

    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    sts_stub.add_response(
        "assume_role",
        {
            "Credentials": {
                "AccessKeyId": "ASIADEMOTEMPORARY",
                "SecretAccessKey": "demo-secret",
                "SessionToken": "demo-token",
                "Expiration": expiry,
            },
            "AssumedRoleUser": {
                "AssumedRoleId": "AROADEMO:cost-anomaly",
                "Arn": f"{ROLE_ARN.replace(':iam:', ':sts:').replace(':role/', ':assumed-role/')}/cost-anomaly",
            },
        },
        {
            "RoleArn": ROLE_ARN,
            "RoleSessionName": auth.SESSION_NAME,
            "Policy": json.dumps(auth.SESSION_POLICY),
            "DurationSeconds": auth.DEFAULT_DURATION,
            "SerialNumber": MFA_SERIAL,
            "TokenCode": FAKE_MFA,
        },
    )

    # Two pages, like a real account with many services × 90 days.
    half = len(results) // 2
    first = build_request(start, end)
    ce_stub.add_response(
        "get_cost_and_usage",
        {"ResultsByTime": results[:half], "NextPageToken": "page-2", "DimensionValueAttributes": []},
        first,
    )
    ce_stub.add_response(
        "get_cost_and_usage",
        {"ResultsByTime": results[half:], "DimensionValueAttributes": []},
        {**first, "NextPageToken": "page-2"},
    )

    def session_factory(**kwargs):
        if "profile_name" in kwargs:
            step(f"Source profile '{kwargs['profile_name']}' → sts:AssumeRole {ROLE_ARN}")
            step(f"Session policy: {json.dumps(auth.SESSION_POLICY['Statement'][0])}")
            return FakeSession(sts)
        step(f"Got temporary credentials {kwargs['aws_access_key_id']} (Cost Explorer read-only)")
        return FakeSession(ce)

    def fake_prompt(msg):
        print(f"    {msg}{FAKE_MFA}  (simulated)")
        return FAKE_MFA

    def fake_assume_role_session(profile):
        return auth.assume_role_session(profile, prompt=fake_prompt, session_factory=session_factory)

    cli.assume_role_session = fake_assume_role_session
    ce.meta.events.register(
        "provide-client-params.ce.GetCostAndUsage",
        lambda params, **_: step(
            "ce:GetCostAndUsage " + ("(page 2, NextPageToken)" if "NextPageToken" in params else "(page 1)")
        ),
    )
    sts_stub.activate()
    ce_stub.activate()
    return [sts_stub, ce_stub]


# --------------------------------------------------------------------------- output


def step(msg: str) -> None:
    print(f"  → {msg}")


def header(msg: str) -> None:
    print(f"\n\033[1m{msg}\033[0m")


def print_matrix_summary(matrix, eval_days):
    header("Simulated daily cost in the evaluation window (USD)")
    cols = [d.strftime("%m-%d") for d in eval_days]
    print(f"  {'service':<40}" + "".join(f"{c:>9}" for c in cols))
    for svc, s in sorted(matrix.items()):
        print(f"  {svc[:40]:<40}" + "".join(f"{s[d]:>9.2f}" for d in eval_days))


def print_anomalies(path: Path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    header(f"Anomalies ({len(rows)}) — from {path}")
    print(f"  {'date':<11}{'kind':<13}{'service':<40}{'cost':>9}{'median':>9}{'delta':>9}{'z':>8}")
    for r in rows:
        color = "\033[31m" if r["kind"] == "SPIKE" else "\033[33m"
        print(
            f"  {r['date']:<11}{color}{r['kind']:<13}\033[0m{r['service'][:39]:<40}"
            f"{float(r['cost']):>9.2f}{float(r['baseline_median']):>9.2f}{float(r['delta']):>9.2f}"
            f"{r['robust_z'] or '—':>8}"
        )


SCENARIOS = """\
  • EC2 Compute ×1.7 for one day            → expect SPIKE
  • EC2 - Other (NAT/data transfer) ×3.5, 2 days → expect 2× SPIKE
  • Amazon Bedrock appears from nothing     → expect NEW_SERVICE each day (< 7 days history)
  • AWS Lambda $5 → $12 (z high, +$7)       → filtered by --min-delta 10
  • S3 grows slowly over 90 days            → trend, no alert
  • RDS, CloudWatch steady                  → no alert"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--end-date", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    p.add_argument("--output", type=Path, default=Path(__file__).parent / "demo_anomalies.csv")
    args = p.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="cost-anomaly-demo-"))
    write_aws_config(tmp / "config")
    for var in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_SESSION_TOKEN"):
        os.environ.pop(var, None)
    os.environ.update(
        AWS_CONFIG_FILE=str(tmp / "config"),
        AWS_SHARED_CREDENTIALS_FILE=str(tmp / "missing-credentials"),
        AWS_EC2_METADATA_DISABLED="true",
    )

    windows = compute_windows(args.end_date, Settings())
    days = date_range(windows.fetch_start, windows.fetch_end)
    matrix = simulate_costs(days, windows.eval_days)

    header("cost-anomaly — offline demo (no AWS calls)")
    print(f"  Fetch window : {windows.fetch_start} → {windows.fetch_end} (exclusive), {len(days)} days")
    print(f"  Evaluate     : {windows.eval_days[0]} → {windows.eval_days[-1]} (last 2 days skipped: CE still settling)")
    print(f"  Baseline     : 30 days before each evaluated day, median + MAD")
    header("Planted scenarios")
    print(SCENARIOS)
    print_matrix_summary(matrix, windows.eval_days)

    stubs = install_fake_aws(to_results(matrix, days), windows.fetch_start, windows.fetch_end)
    header(f"Running: cost-anomaly --profile {PROFILE} --end-date {args.end_date} --output {args.output}")
    code = cli.main(["--profile", PROFILE, "--end-date", args.end_date.isoformat(), "--output", str(args.output)])
    for s in stubs:
        s.assert_no_pending_responses()
    if code != 0:
        return code

    print_anomalies(args.output)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
