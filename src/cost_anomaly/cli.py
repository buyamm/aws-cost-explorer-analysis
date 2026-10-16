import argparse
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from botocore.exceptions import BotoCoreError

from .analysis import build_report
from .auth import AuthError, assume_role_session
from .config import Settings
from .dates import compute_windows
from .detect import detect
from .fetch import CostExplorerError, TooManyPages, fetch_daily_costs
from .guard import install_guard
from .html_report import write_html
from .md_report import write_markdown
from .report import write_csv
from .transform import to_matrix

defaults = Settings()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Detect daily per-service AWS cost spikes (Cost Explorer).")
    p.add_argument(
        "--profile",
        default=os.environ.get("AWS_PROFILE"),
        help="switch-role profile (role_arn + source_profile [+ mfa_serial]); default: $AWS_PROFILE",
    )
    p.add_argument("--output", type=Path, default=Path("anomalies.csv"))
    p.add_argument("--k", type=float, default=defaults.k, help="robust z-score threshold")
    p.add_argument("--min-delta", type=float, default=defaults.min_delta, help="USD above baseline median")
    p.add_argument("--new-threshold", type=float, default=defaults.new_threshold, help="USD/day for new services")
    p.add_argument("--min-history", type=int, default=defaults.min_history, help="non-zero baseline days for MAD")
    p.add_argument("--max-pages", type=int, default=defaults.max_pages, help="cap on Cost Explorer requests")
    p.add_argument(
        "--end-date",
        type=date.fromisoformat,
        help="exclusive end of the fetch window, YYYY-MM-DD (default: today UTC)",
    )
    p.add_argument(
        "--no-report",
        action="store_true",
        help="only write the CSV (skip <output>_report.html and <output>_report.md)",
    )
    args = p.parse_args(argv)
    if not args.profile:
        p.error("--profile is required (or set AWS_PROFILE)")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings(
        k=args.k,
        min_delta=args.min_delta,
        new_threshold=args.new_threshold,
        min_history=args.min_history,
        max_pages=args.max_pages,
    )
    today = args.end_date or datetime.now(timezone.utc).date()
    windows = compute_windows(today, settings)

    try:
        session = assume_role_session(args.profile)
        client = install_guard(session.client("ce", region_name="us-east-1"))
        results = fetch_daily_costs(client, windows.fetch_start, windows.fetch_end, settings.max_pages)
    except (AuthError, BotoCoreError, CostExplorerError, TooManyPages) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    matrix = to_matrix(results, windows.fetch_start, windows.fetch_end)
    anomalies = detect(matrix, windows.eval_days, settings)
    write_csv(anomalies, args.output)
    print(f"Found {len(anomalies)} anomalies → {args.output}")

    if not args.no_report:
        html_path, md_path = report_paths(args.output)
        report = build_report(matrix, windows, settings, anomalies, args.profile, datetime.now(timezone.utc))
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
