"""Slack incoming-webhook alerts for new or worsened incidents."""

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Callable
from urllib.parse import urlsplit

from .analysis import PROVISIONAL_LABEL, RATE_LABEL, usd
from .detect import RATE
from .state import NEW, Change

WEBHOOK_ENV = "COST_ANOMALY_SLACK_WEBHOOK"
SLACK_HOST = "hooks.slack.com"
MAX_LISTED = 10
TIMEOUT = 10  # seconds
ATTEMPTS = 3


class AlertError(RuntimeError):
    pass


def webhook_from_env(environ: Mapping[str, str] = os.environ) -> str | None:
    return environ.get(WEBHOOK_ENV, "").strip() or None


def validate_webhook(url: str) -> None:
    """Only Slack over HTTPS, so a mistyped or tampered variable can't ship cost data elsewhere.

    Errors never include the URL: it is a secret.
    """
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != SLACK_HOST:
        raise AlertError(f"{WEBHOOK_ENV} must be a Slack incoming webhook (https://{SLACK_HOST}/...)")


def escape(text: str) -> str:
    """Slack mrkdwn control characters; service names are untrusted."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def describe(change: Change) -> str:
    i = change.incident
    days = i.start.isoformat() if i.start == i.end else f"{i.start.isoformat()} → {i.end.isoformat()}"
    move = f"vượt {usd(i.peak_delta)}" if i.peak_delta >= 0 else f"giảm {usd(-i.peak_delta)}"
    sign = "+" if i.month_impact >= 0 else ""
    labels = [RATE_LABEL] * (i.driver == RATE) + [PROVISIONAL_LABEL] * i.provisional
    tags = f" · _{', '.join(labels)}_" if labels else ""
    return (
        f"*{i.kind} · {escape(i.service)}* ({'mới' if change.reason == NEW else 'xấu đi'})\n"
        f"{days} · {move}/ngày · nếu tiếp diễn {sign}{usd(i.month_impact)} tháng này{tags}"
    )


def build_message(changes: list[Change], profile: str, location: str | None) -> dict:
    ordered = sorted(changes, key=lambda c: abs(c.incident.month_impact), reverse=True)
    n = len(changes)
    blocks: list[dict] = [{"type": "header", "text": {"type": "plain_text", "text": f"Chi phí AWS bất thường: {n} sự cố"}}]
    blocks += [{"type": "section", "text": {"type": "mrkdwn", "text": describe(c)}} for c in ordered[:MAX_LISTED]]
    context = [f"Profile `{escape(profile)}`"]
    if n > MAX_LISTED:
        context.append(f"và {n - MAX_LISTED} sự cố khác")
    if location:
        context.append(f"Report: {escape(location)}")
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": " · ".join(context)}]})
    return {"text": f"cost-anomaly: {n} sự cố chi phí mới/xấu đi (profile {profile})", "blocks": blocks}


def send(
    url: str,
    payload: dict,
    opener: Callable | None = None,
    sleep: Callable[[float], None] | None = None,
) -> None:
    """POST the payload; retry network errors, 429 and 5xx with backoff (1 s, 2 s)."""
    validate_webhook(url)
    # Looked up at call time so tests can replace the network layer.
    opener, sleep = opener or urllib.request.urlopen, sleep or time.sleep
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in range(1, ATTEMPTS + 1):
        request = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
        try:
            with opener(request, timeout=TIMEOUT):
                return
        except urllib.error.HTTPError as e:
            # str(HTTPError) carries no URL, but build the message ourselves to be sure.
            error, retry = f"Slack returned HTTP {e.code}", e.code == 429 or e.code >= 500
        except (urllib.error.URLError, TimeoutError) as e:
            error, retry = f"cannot reach Slack: {getattr(e, 'reason', e)}", True
        if not retry or attempt == ATTEMPTS:
            raise AlertError(error)
        sleep(attempt)
