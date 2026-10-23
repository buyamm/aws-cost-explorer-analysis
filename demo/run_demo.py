"""Offline demo: run the real cost-anomaly CLI against simulated AWS.

Nothing here talks to AWS. The demo writes a throwaway AWS config, answers the MFA
prompt itself, and stubs STS + Cost Explorer with botocore's Stubber, feeding 90 days
of synthetic per-service costs with a few planted scenarios.

    uv run python demo/run_demo.py [--end-date 2026-10-15] [--output demo/demo_anomalies.csv] [--pdf]
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
from botocore.stub import Stubber

from cost_anomaly import auth, cli
from cost_anomaly.cad import build_request as cad_request
from cost_anomaly.config import Settings
from cost_anomaly.dates import compute_windows, date_range
from cost_anomaly.fetch import build_request
from cost_anomaly.guard import ALLOWED_OPERATIONS, CAD_OPERATIONS

PROFILE = "project-cost"
ROLE_ARN = "arn:aws:iam::111122223333:role/CostReader"
MFA_SERIAL = "arn:aws:iam::444455556666:mfa/demo-device"
FAKE_MFA = "123456"
DUMMY_KEYS = {"aws_access_key_id": "DEMO", "aws_secret_access_key": "DEMO"}


# --------------------------------------------------------------------------- data


Matrix = dict[str, dict[date, float]]


def simulate_costs(days: list[date], windows, seed: int = 7) -> tuple[Matrix, Matrix]:
    """Synthetic (usage, amortized) daily costs per service, with scenarios planted in the eval window."""
    rng = random.Random(seed)
    e = [d for d in windows.eval_days if d not in windows.provisional_days]  # settled, oldest first, 7 days
    p = windows.provisional_days  # T−2, T−1

    def series(base: float, noise: float, weekend: float = 1.0, trend: float = 0.0) -> dict[date, float]:
        out = {}
        for i, d in enumerate(days):
            v = (base + trend * i) * (weekend if d.weekday() >= 5 else 1.0)
            out[d] = round(max(v * (1 + rng.gauss(0, noise)), 0.0), 4)
        return out

    m = {
        "Amazon Elastic Compute Cloud - Compute": series(320, 0.03, weekend=0.85),
        "EC2 - Other": series(25, 0.05),
        "Amazon Relational Database Service": series(180, 0.005),
        "Amazon Simple Storage Service": series(40, 0.02, trend=0.17),
        "AWS Lambda": series(5, 0.08),
        "AmazonCloudWatch": series(12, 0.04),
        "Amazon Bedrock": {d: 0.0 for d in days},
        "AWS Fargate": series(80, 0.01),
        "Amazon ElastiCache": {d: 0.0 for d in days},
        "AWS Backup": series(40, 0.02),
    }

    # 1. EC2 compute spike (someone launched a fleet of large on-demand instances for a day)
    ec2 = "Amazon Elastic Compute Cloud - Compute"
    normal_ec2 = m[ec2][e[5]]
    m[ec2][e[5]] = 540.0
    # 2. NAT Gateway / data transfer surge for two days
    m["EC2 - Other"][e[3]] = 96.5
    m["EC2 - Other"][e[4]] = 88.2
    # 3. New service: Bedrock starts being used mid-window
    for i, d in enumerate(e[1:]):
        m["Amazon Bedrock"][d] = round(30 + 8 * i + rng.uniform(-2, 2), 4)
    # 4. Lambda doubles, but +$7 stays under --min-delta → filtered as noise
    m["AWS Lambda"][e[2]] = 12.0
    # 5. RDS +$7 for a day: only reported because the config sets min_delta = 5 for RDS
    m["Amazon Relational Database Service"][e[1]] += 7.0
    # 6. Backup jobs stop: AWS Backup falls to $0 from e[5] and stays there → DROP
    for d in e[5:] + p:
        m["AWS Backup"][d] = 0.0
    # 7. CloudWatch log ingestion explodes yesterday: provisional data
    m["AmazonCloudWatch"][p[-1]] = 64.0

    # What was actually paid. Uncovered services pay the usage cost.
    paid = {svc: dict(s) for svc, s in m.items()}
    # EC2 Compute is 25% Savings Plan covered at a 40% discount: pays 90% of the on-demand equivalent;
    # the extra fleet on e[5] is on-demand, so it adds the same dollars to both measures.
    paid[ec2] = {d: round(v * 0.9, 4) for d, v in m[ec2].items()}
    paid[ec2][e[5]] = round(normal_ec2 * 0.9 + 540.0 - normal_ec2, 4)
    # 8. Fargate Savings Plan expires: usage flat, paid goes from 65% of on-demand to 100%
    paid["AWS Fargate"] = {d: round(v * (1.0 if d >= e[2] else 0.65), 4) for d, v in m["AWS Fargate"].items()}
    # 9. ElastiCache fully covered by a Reserved Instance (usage measure $0, RI cost $60/day) until it expires
    for d in days:
        expired = d >= e[4]
        m["Amazon ElastiCache"][d] = round(95.0 * (1 + rng.gauss(0, 0.01)), 4) if expired else 0.0
        paid["Amazon ElastiCache"][d] = m["Amazon ElastiCache"][d] if expired else round(60 * (1 + rng.gauss(0, 0.01)), 4)
    # S3 grows slowly the whole time → trend, not a spike → no alert
    return m, paid


def to_results(usage: Matrix, paid: Matrix, days: list[date]) -> list[dict]:
    def metrics(svc: str, d: date) -> dict:
        return {
            "UnblendedCost": {"Amount": f"{usage[svc][d]:.4f}", "Unit": "USD"},
            "NetAmortizedCost": {"Amount": f"{paid[svc][d]:.4f}", "Unit": "USD"},
        }

    return [
        {
            "TimePeriod": {"Start": d.isoformat(), "End": (d + timedelta(days=1)).isoformat()},
            "Total": {},
            "Groups": [
                {"Keys": [svc], "Metrics": metrics(svc, d)}
                for svc in sorted(usage)
                if usage[svc][d] > 0 or paid[svc][d] > 0
            ],
            "Estimated": d >= days[-2],
        }
        for d in days
    ]


def simulate_cad(windows) -> dict:
    """What AWS Cost Anomaly Detection would return: two findings the tool also has, one it doesn't."""
    e = [d for d in windows.eval_days if d not in windows.provisional_days]
    monitor = "arn:aws:ce::111122223333:anomalymonitor/aws-services"

    def finding(id_, service, start, end, impact, score):
        a = {
            "AnomalyId": id_,
            "AnomalyStartDate": start.isoformat(),
            "DimensionValue": service,
            "RootCauses": [{"Service": service, "Region": "us-east-1"}],
            "AnomalyScore": {"MaxScore": score, "CurrentScore": score},
            "Impact": {"MaxImpact": impact, "TotalImpact": impact},
            "MonitorArn": monitor,
        }
        if end:
            a["AnomalyEndDate"] = end.isoformat()
        return a

    return {
        "Anomalies": [
            finding("cad-ec2", "Amazon Elastic Compute Cloud - Compute", e[5], e[5], 225.0, 0.91),
            finding("cad-cache", "Amazon ElastiCache", e[4], None, 380.0, 0.84),  # still open
            finding("cad-s3", "Amazon Simple Storage Service", e[1], e[3], 9.8, 0.55),  # tool sees a trend, not a spike
        ]
    }


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


def install_fake_aws(
    results: list[dict], start: date, end: date, operations=ALLOWED_OPERATIONS, cad: dict | None = None
) -> list[Stubber]:
    """Patch cli.assume_role_session so the real auth code runs against stubbed STS/CE."""
    policy = auth.session_policy(operations)
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
            "Policy": json.dumps(policy),
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
    if cad is not None:
        w = compute_windows(end, Settings())
        ce_stub.add_response("get_anomalies", cad, cad_request(w.eval_days[0], w.eval_days[-1]))

    def session_factory(**kwargs):
        if "profile_name" in kwargs:
            step(f"Source profile '{kwargs['profile_name']}' → sts:AssumeRole {ROLE_ARN}")
            step(f"Session policy: {json.dumps(policy['Statement'][0])}")
            return FakeSession(sts)
        step(f"Got temporary credentials {kwargs['aws_access_key_id']} (Cost Explorer read-only)")
        return FakeSession(ce)

    def fake_prompt(msg):
        print(f"    {msg}{FAKE_MFA}  (simulated)")
        return FAKE_MFA

    def fake_assume_role_session(profile, operations=ALLOWED_OPERATIONS):
        return auth.assume_role_session(profile, prompt=fake_prompt, session_factory=session_factory, operations=operations)

    cli.assume_role_session = fake_assume_role_session
    ce.meta.events.register(
        "provide-client-params.ce.GetAnomalies", lambda params, **_: step("ce:GetAnomalies (AWS CAD, --with-cad)")
    )
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


def print_matrix_summary(matrix, eval_days, title="Simulated daily usage cost in the evaluation window (USD)"):
    header(title)
    cols = [d.strftime("%m-%d") for d in eval_days]
    print(f"  {'service':<40}" + "".join(f"{c:>9}" for c in cols))
    for svc, s in sorted(matrix.items()):
        print(f"  {svc[:40]:<40}" + "".join(f"{s[d]:>9.2f}" for d in eval_days))


def print_anomalies(path: Path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    header(f"Anomalies ({len(rows)}) — from {path}")
    print(
        f"  {'date':<11}{'kind':<13}{'service':<40}{'cost':>9}{'median':>9}{'delta':>9}{'z':>8}{'month':>10}"
        f"  {'metric':<10}{'driver':<7}{'prov.':<6}known"
    )
    for r in rows:
        color = {"SPIKE": "\033[31m", "DROP": "\033[35m"}.get(r["kind"], "\033[33m")
        print(
            f"  {r['date']:<11}{color}{r['kind']:<13}\033[0m{r['service'][:39]:<40}"
            f"{float(r['cost']):>9.2f}{float(r['baseline_median']):>9.2f}{float(r['delta']):>9.2f}"
            f"{r['robust_z'] or '—':>8}{float(r['month_impact']):>10.2f}  {r['metric']:<10}{r['driver']:<7}"
            f"{r['provisional']:<6}{r['known']}"
        )


SCENARIOS = """\
  • EC2 Compute ×1.7 for one day (on-demand) → expect SPIKE, driver=usage
  • EC2 - Other (NAT/data transfer) ×3.5, 2 days → expect 2× SPIKE
  • Amazon Bedrock appears from nothing     → expect NEW_SERVICE each day (< 7 days history)
  • AWS Lambda $5 → $12 (z high, +$7)       → filtered by --min-delta 10
  • S3 grows slowly over 90 days            → trend, no alert
  • Fargate Savings Plan expires, usage flat → expect amortized SPIKE, driver=rate (not a usage spike)
  • ElastiCache RI expires ($0 usage → $95) → expect SPIKE, driver=rate (not NEW_SERVICE)
  • CloudWatch $12 → $64 yesterday (T−1)    → expect SPIKE, provisional=true
  • RDS +$7 for a day (config min_delta = 5) → expect SPIKE (Lambda's +$7 stays filtered)
  • AWS Backup $40 → $0 from day 6, ongoing → expect DROP, negative month_impact
  • Bedrock is listed as known               → its rows have known=true
  (config: demo/cost-anomaly.toml)
  Two runs share a --state file: yesterday records the incidents, today only the new/worse
  ones (the CloudWatch spike of T−1) appear in the Slack payload.
  Run 2 also uses --with-cad: EC2 Compute and ElastiCache match AWS CAD, S3 is CAD-only."""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--end-date", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    p.add_argument("--output", type=Path, default=Path(__file__).parent / "demo_anomalies.csv")
    p.add_argument("--pdf", action="store_true", help="also print the report to PDF (needs Chrome, Chromium or Edge)")
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
    # One extra day at the start so yesterday's run has a full 90-day window too.
    days = date_range(windows.fetch_start - timedelta(days=1), windows.fetch_end)
    matrix, paid = simulate_costs(days, windows)

    header("cost-anomaly — offline demo (no AWS calls)")
    print(f"  Fetch window : {windows.fetch_start} → {windows.fetch_end} (exclusive), {len(days) - 1} days")
    print(
        f"  Evaluate     : {windows.eval_days[0]} → {windows.eval_days[-1]} "
        f"(last 2 days provisional: CE still settling)"
    )
    print(f"  Baseline     : 30 days before each evaluated day, median + MAD")
    header("Planted scenarios")
    print(SCENARIOS)
    print_matrix_summary(matrix, windows.eval_days)
    print_matrix_summary(paid, windows.eval_days, "Simulated amortized (actually paid) cost (USD)")

    config = str(Path(__file__).parent / "cost-anomaly.toml")
    state = str(tmp / "state.json")
    yesterday = args.end_date - timedelta(days=1)

    header(f"Run 1 — yesterday ({yesterday}): record incidents in {state}")
    code = run_cli(matrix, paid, yesterday, ["--output", str(tmp / "yesterday.csv"), "--no-report", "--config", config, "--state", state])
    if code != 0:
        return code

    header(f"Run 2 — today ({args.end_date}): only new or worse incidents reach Slack (dry run), cross-checked with AWS CAD")
    extra = ["--output", str(args.output), "--config", config, "--state", state, "--alert-dry-run", "--with-cad"] + ["--pdf"] * args.pdf
    code = run_cli(matrix, paid, args.end_date, extra, cad=simulate_cad(windows))
    if code != 0:
        return code

    print_anomalies(args.output)
    print()
    return 0


def run_cli(usage: Matrix, paid: Matrix, end: date, extra: list[str], cad: dict | None = None) -> int:
    """Run the real CLI for one end date against freshly stubbed AWS."""
    w = compute_windows(end, Settings())
    results = to_results(usage, paid, date_range(w.fetch_start, w.fetch_end))
    operations = CAD_OPERATIONS if cad is not None else ALLOWED_OPERATIONS
    stubs = install_fake_aws(results, w.fetch_start, w.fetch_end, operations, cad)
    argv = ["--profile", PROFILE, "--end-date", end.isoformat(), *extra]
    print(f"  $ cost-anomaly {' '.join(argv)}")
    code = cli.main(argv)
    for s in stubs:
        s.assert_no_pending_responses()
    return code


if __name__ == "__main__":
    sys.exit(main())
