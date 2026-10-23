import argparse
import os
import sys
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

from botocore.exceptions import BotoCoreError

from .analysis import build_report
from .auth import AuthError, assume_role_session
from .config import Settings
from .fetch import CostExplorerError, TooManyPages
from .html_report import write_html
from .md_report import write_markdown
from .pipeline import run
from .report import write_csv
from .settings_file import ConfigError, load_config

defaults = Settings()
# Every evaluated day needs a full baseline inside the fetched lookback window.
MAX_EVAL_DAYS = defaults.lookback_days - defaults.baseline_days - defaults.exclude_recent_days


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Detect daily per-service AWS cost spikes (Cost Explorer).")
    p.add_argument(
        "--profile",
        default=os.environ.get("AWS_PROFILE"),
        help="switch-role profile (role_arn + source_profile [+ mfa_serial]); default: $AWS_PROFILE",
    )
    p.add_argument("--output", type=Path, default=Path("anomalies.csv"))
    # Thresholds default to None so an explicit flag can override the config file's [defaults].
    p.add_argument("--k", type=float, help=f"robust z-score threshold (default {defaults.k:g})")
    p.add_argument("--min-delta", type=float, help=f"USD above baseline median (default {defaults.min_delta:g})")
    p.add_argument("--new-threshold", type=float, help=f"USD/day for new services (default {defaults.new_threshold:g})")
    p.add_argument("--min-history", type=int, help=f"non-zero baseline days for MAD (default {defaults.min_history})")
    p.add_argument(
        "--config",
        type=Path,
        help="TOML file with [defaults], per-service [services.\"<name>\"] thresholds, ignore and known lists",
    )
    p.add_argument(
        "--eval-days",
        type=int,
        default=defaults.eval_days,
        help=f"number of days to evaluate, 1-{MAX_EVAL_DAYS}",
    )
    p.add_argument("--max-pages", type=int, default=defaults.max_pages, help="cap on Cost Explorer requests")
    p.add_argument(
        "--end-date",
        type=date.fromisoformat,
        help="exclusive end of the fetch window, YYYY-MM-DD (default: today UTC)",
    )
    p.add_argument(
        "--no-provisional",
        action="store_true",
        help="skip the 2 most recent days instead of evaluating them as provisional (not settled in Cost Explorer)",
    )
    p.add_argument("--no-drop", action="store_true", help="do not report services that fall to near zero (DROP)")
    p.add_argument(
        "--no-report",
        action="store_true",
        help="only write the CSV (skip <output>_report.html and <output>_report.md)",
    )
    args = p.parse_args(argv)
    if not args.profile:
        p.error("--profile is required (or set AWS_PROFILE)")
    if not 1 <= args.eval_days <= MAX_EVAL_DAYS:
        p.error(f"--eval-days must be between 1 and {MAX_EVAL_DAYS}")
    return args


def build_settings(args: argparse.Namespace) -> Settings:
    """Built-in defaults → config [defaults] → explicit flags; per-service overrides apply on top."""
    settings = Settings(
        eval_days=args.eval_days,
        max_pages=args.max_pages,
        include_provisional=not args.no_provisional,
        detect_drops=not args.no_drop,
    )
    if args.config:
        settings = load_config(args.config, settings)
    flags = {"k": args.k, "min_delta": args.min_delta, "new_threshold": args.new_threshold, "min_history": args.min_history}
    return replace(settings, **{name: value for name, value in flags.items() if value is not None})


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        settings = build_settings(args)
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    today = args.end_date or datetime.now(timezone.utc).date()

    try:
        session = assume_role_session(args.profile)
        result = run(session, settings, today)
    except (AuthError, BotoCoreError, CostExplorerError, TooManyPages) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    anomalies = result.anomalies
    write_csv(anomalies, args.output)
    print(f"Found {len(anomalies)} anomalies → {args.output}")

    if not args.no_report:
        html_path, md_path = report_paths(args.output)
        now = datetime.now(timezone.utc)
        report = build_report(result.usage, result.windows, settings, anomalies, args.profile, now, result.amortized)
        write_html(report, html_path)
        write_markdown(report, md_path)
        print(f"Report → {html_path}, {md_path}")
    return 0


def report_paths(output: Path) -> tuple[Path, Path]:
    """anomalies.csv → anomalies_report.html, anomalies_report.md (next to the CSV)."""
    stem = output.with_suffix("").name + "_report"
    return output.with_name(stem + ".html"), output.with_name(stem + ".md")


if __name__ == "__main__":
    sys.exit(main())
