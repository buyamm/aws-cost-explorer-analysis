"""Scheduled run on AWS Lambda: execution-role credentials, state and reports in S3, webhook in SSM.

Environment: STATE_BUCKET, STATE_KEY, REPORT_PREFIX, SLACK_WEBHOOK_PARAMETER (optional),
WITH_CAD ("true"/"false"), COST_ANOMALY_CONFIG (TOML text, optional), ACCOUNT_LABEL.
"""

import logging
import os
import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import boto3

from .alert import build_message, send, validate_webhook
from .alerting import process
from .analysis import build_report, usd
from .config import Settings
from .guard import install_guard
from .html_report import render_html
from .md_report import render_markdown
from .pipeline import run
from .report import write_csv
from .settings_file import parse_config
from .state import Change, S3StateStore

S3_OPERATIONS = frozenset({"GetObject", "PutObject"})
SSM_OPERATIONS = frozenset({"GetParameter"})

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def handler(event, context) -> dict:
    return run_scheduled(os.environ, boto3.Session(), datetime.now(timezone.utc))


def guarded_s3(session):
    return install_guard(session.client("s3"), S3_OPERATIONS)


def guarded_ssm(session):
    return install_guard(session.client("ssm"), SSM_OPERATIONS)


def run_scheduled(env: Mapping[str, str], session, now: datetime) -> dict:
    """Everything local or cheap is checked before the billable Cost Explorer request."""
    settings = Settings()
    if env.get("COST_ANOMALY_CONFIG"):
        settings = parse_config(env["COST_ANOMALY_CONFIG"], settings, "COST_ANOMALY_CONFIG")
    with_cad = env.get("WITH_CAD", "false").lower() == "true"
    bucket = env["STATE_BUCKET"]
    label = env.get("ACCOUNT_LABEL") or "lambda"
    today = now.date()

    webhook = None
    if env.get("SLACK_WEBHOOK_PARAMETER"):
        response = guarded_ssm(session).get_parameter(Name=env["SLACK_WEBHOOK_PARAMETER"], WithDecryption=True)
        webhook = response["Parameter"]["Value"].strip()
        validate_webhook(webhook)

    s3 = guarded_s3(session)
    store = S3StateStore(s3, bucket, env.get("STATE_KEY", "state/incidents.json"))
    state = store.load()  # a corrupt state object fails the run here, before any request is billed

    result = run(session, settings, today, with_cad=with_cad)
    if result.cad_error:
        log.warning("AWS CAD unavailable, continuing without it: %s", result.cad_error)

    prefix = f"{env.get('REPORT_PREFIX', 'reports/')}{today.isoformat()}/"
    report = build_report(
        result.usage, result.windows, settings, result.anomalies, label, now, result.amortized,
        result.cad, result.cad_error,
    )
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "anomalies.csv"
        write_csv(result.anomalies, csv_path)
        files = {
            "anomalies.csv": (csv_path.read_bytes(), "text/csv; charset=utf-8"),
            "anomalies_report.html": (render_html(report).encode("utf-8"), "text/html; charset=utf-8"),
            "anomalies_report.md": (render_markdown(report).encode("utf-8"), "text/markdown; charset=utf-8"),
        }
    for name, (body, content_type) in files.items():
        s3.put_object(Bucket=bucket, Key=prefix + name, Body=body, ContentType=content_type)
    location = f"s3://{bucket}/{prefix}anomalies_report.html"

    def deliver(changes: list[Change]) -> None:
        if webhook:
            send(webhook, build_message(changes, label, location))
            log.info("Slack: sent %d new/worse incident(s)", len(changes))
            return
        for c in changes:
            i = c.incident
            log.info("%s %s %s %s → %s peak %s/day", c.reason, i.kind, i.service, i.start, i.end, usd(i.peak_delta))

    changes = process(result.anomalies, settings, result.windows.fetch_start, store, deliver, now.isoformat(), state=state)
    return {
        "date": today.isoformat(),
        "anomalies": len(result.anomalies),
        "alerted": len(changes),
        "cad_error": result.cad_error,
        "reports": f"s3://{bucket}/{prefix}",
    }
